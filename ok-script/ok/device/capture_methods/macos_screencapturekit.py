"""Game window capture through ScreenCaptureKit, Apple's current capture API.

Apple deprecated ``CGWindowListCreateImage``, which
:class:`MacOSQuartzCaptureMethod` uses, in macOS 14. This method streams the
game window with an ``SCStream`` instead and keeps the most recent frame. It
converts a frame to a numpy array only when a task asks for one.

It falls back to Quartz capture when ScreenCaptureKit isn't usable:

- on macOS 13 and older;
- when the pyobjc bindings are missing;
- while the stream is starting;
- after the stream fails, for example when Screen Recording permission is
  missing. It retries after ``RETRY_AFTER`` seconds.

Set ``OK_MAC_CAPTURE=quartz`` to always use Quartz capture.
"""

import os
import threading
import time

import numpy as np

from ok.device.capture_methods.macos_quartz import MacOSQuartzCaptureMethod
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

try:
    import CoreMedia
    import Quartz
    import ScreenCaptureKit
    from Foundation import NSObject
    import objc
except Exception as e:  # not macOS, or the pyobjc frameworks are not installed
    CoreMedia = Quartz = ScreenCaptureKit = NSObject = objc = None
    logger.debug(f"ScreenCaptureKit is not importable: {e}")

try:
    import dispatch
except Exception:
    dispatch = None

FRAMES_PER_SECOND = 60
QUEUE_DEPTH = 5
START_TIMEOUT = 3.0
# How long do_get_frame waits for a frame newer than the one it returned last.
NEW_FRAME_WAIT = 1.0 / 30
# A stream that delivers nothing for this long counts as failed.
FIRST_FRAME_TIMEOUT = 2.0
RETRY_AFTER = 30.0
_FALLBACK = object()


def available():
    """True when ScreenCaptureKit window streams can be used here (macOS 14+)."""
    if os.environ.get("OK_MAC_CAPTURE", "").strip().lower() == "quartz":
        return False
    if ScreenCaptureKit is None or CoreMedia is None or Quartz is None:
        return False
    try:
        # setIgnoreShadowsSingleWindow: (macOS 14) keeps the frame the same
        # size as the window, so the Quartz geometry and crop logic still apply.
        return bool(ScreenCaptureKit.SCStreamConfiguration.instancesRespondToSelector_(
            b"setIgnoreShadowsSingleWindow:"))
    except Exception:
        return False


def pixel_buffer_to_bgr(pixel_buffer):
    """Copy a 32BGRA CVPixelBuffer into an (h, w, 3) BGR uint8 array."""
    Quartz.CVPixelBufferLockBaseAddress(pixel_buffer, Quartz.kCVPixelBufferLock_ReadOnly)
    try:
        width = Quartz.CVPixelBufferGetWidth(pixel_buffer)
        height = Quartz.CVPixelBufferGetHeight(pixel_buffer)
        bytes_per_row = Quartz.CVPixelBufferGetBytesPerRow(pixel_buffer)
        base = Quartz.CVPixelBufferGetBaseAddress(pixel_buffer)
        if base is None or width <= 0 or height <= 0:
            return None
        buf = np.frombuffer(base.as_buffer(bytes_per_row * height), dtype=np.uint8)
        return buf.reshape((height, bytes_per_row // 4, 4))[:, :width, :3].copy()
    finally:
        Quartz.CVPixelBufferUnlockBaseAddress(pixel_buffer, Quartz.kCVPixelBufferLock_ReadOnly)


def _frame_is_complete(sample_buffer):
    attachments = CoreMedia.CMSampleBufferGetSampleAttachmentsArray(sample_buffer, False)
    if not attachments:
        return False
    status = attachments[0].get(ScreenCaptureKit.SCStreamFrameInfoStatus)
    return status is not None and int(status) == ScreenCaptureKit.SCFrameStatusComplete


def _wait_for(start, timeout):
    """Call start(done) with a completion callback and wait for it; returns (args, finished)."""
    finished = threading.Event()
    result = []

    def done(*args):
        result.extend(args)
        finished.set()

    start(done)
    return result, finished.wait(timeout)


_Output = None


def _output_class():
    """Define the Objective-C stream output class once, on first use."""
    global _Output
    if _Output is None:
        protocols = [objc.protocolNamed("SCStreamOutput"), objc.protocolNamed("SCStreamDelegate")]

        class OkScreenCaptureKitOutput(NSObject, protocols=protocols):
            def initWithStream_(self, owner):
                self = objc.super(OkScreenCaptureKitOutput, self).init()
                if self is None:
                    return None
                self.owner = owner
                return self

            def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
                if output_type == ScreenCaptureKit.SCStreamOutputTypeScreen:
                    self.owner.on_sample(sample_buffer)

            def stream_didStopWithError_(self, stream, error):
                self.owner.on_stopped(error)

        _Output = OkScreenCaptureKitOutput
    return _Output


class WindowStream:
    """One SCStream on one window. Keeps the newest complete sample buffer."""

    def __init__(self, window_id, width, height):
        self.window_id = window_id
        self.size = (width, height)
        self.error = None
        self.started_at = 0.0
        self._cond = threading.Condition()
        self._sample = None
        self._seq = 0
        self._stream = None
        self._output = None
        self._queue = None

    def start(self):
        """Start the stream; returns False (with self.error set) if it can't."""
        content, ok = _wait_for(
            lambda done: ScreenCaptureKit.SCShareableContent
            .getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(True, False, done),
            START_TIMEOUT)
        if not ok or not content or content[0] is None:
            self.error = content[1] if len(content) > 1 and content[1] is not None else "no shareable content"
            return False
        window = next((w for w in content[0].windows() if int(w.windowID()) == int(self.window_id)), None)
        if window is None:
            self.error = f"window {self.window_id} is not shareable"
            return False

        content_filter = ScreenCaptureKit.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)
        self._output = _output_class().alloc().initWithStream_(self)
        self._stream = ScreenCaptureKit.SCStream.alloc().initWithFilter_configuration_delegate_(
            content_filter, self._configuration(*self.size), self._output)
        if dispatch is not None:
            self._queue = dispatch.dispatch_queue_create(b"ok.screencapturekit", None)
        added, error = self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._output, ScreenCaptureKit.SCStreamOutputTypeScreen, self._queue, None)
        if not added:
            self.error = error or "addStreamOutput failed"
            return False
        result, ok = _wait_for(self._stream.startCaptureWithCompletionHandler_, START_TIMEOUT)
        if not ok or (result and result[0] is not None):
            self.error = result[0] if result else "start timed out"
            return False
        self.started_at = time.time()
        return True

    @staticmethod
    def _configuration(width, height):
        config = ScreenCaptureKit.SCStreamConfiguration.alloc().init()
        config.setWidth_(int(width))
        config.setHeight_(int(height))
        config.setPixelFormat_(Quartz.kCVPixelFormatType_32BGRA)
        config.setShowsCursor_(False)
        config.setQueueDepth_(QUEUE_DEPTH)
        config.setIgnoreShadowsSingleWindow_(True)
        config.setMinimumFrameInterval_(CoreMedia.CMTimeMakeWithEpoch(1, FRAMES_PER_SECOND, 0))
        return config

    def resize(self, width, height):
        if (width, height) == self.size or self._stream is None:
            return
        self.size = (width, height)
        self._stream.updateConfiguration_completionHandler_(self._configuration(width, height), None)

    def stop(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stopCaptureWithCompletionHandler_(None)
            except Exception as e:
                logger.debug(f"stopCapture error: {e}")
        with self._cond:
            self._sample = None
            self._cond.notify_all()

    def on_sample(self, sample_buffer):
        try:
            if not _frame_is_complete(sample_buffer):
                return  # idle frames carry no new image
        except Exception:
            return
        with self._cond:
            self._sample = sample_buffer
            self._seq += 1
            self._cond.notify_all()

    def on_stopped(self, error):
        self.error = error or "stream stopped"
        with self._cond:
            self._cond.notify_all()

    def latest(self, after_seq, timeout):
        """Return (sample_buffer, seq), waiting up to timeout for one newer than after_seq."""
        with self._cond:
            if self._seq <= after_seq and self.error is None:
                self._cond.wait(timeout)
            return self._sample, self._seq


class MacOSScreenCaptureKitMethod(MacOSQuartzCaptureMethod):
    name = "macOS ScreenCaptureKit"
    short_description = "native macOS ScreenCaptureKit window stream"
    description = (
        "\nStreams the game window with ScreenCaptureKit. "
        "\nFalls back to Quartz window capture when ScreenCaptureKit is unavailable."
    )
    stream_class = WindowStream

    def __init__(self, hwnd_window):
        super().__init__(hwnd_window)
        self._stream = None
        self._stream_lock = threading.Lock()
        self._last_seq = 0
        self._retry_at = 0.0

    def do_get_frame(self):
        frame = self._stream_frame()
        if frame is _FALLBACK:
            return super().do_get_frame()
        return frame

    def close(self):
        with self._stream_lock:
            self._stop_stream()
        super().close()

    def _stop_stream(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
        self._last_seq = 0

    def _fail(self, reason):
        logger.warning(f"ScreenCaptureKit capture unavailable, using Quartz capture for "
                       f"{RETRY_AFTER:.0f}s: {reason}")
        self._stop_stream()
        self._retry_at = time.time() + RETRY_AFTER
        return _FALLBACK

    def _stream_frame(self):
        window = self.hwnd_window
        if window is None or window.hwnd <= 0:
            return None
        if (self.exit_event is not None and self.exit_event.is_set()) or time.time() < self._retry_at:
            return _FALLBACK
        width, height = window.window_width, window.window_height
        if width <= 10 or height <= 10:
            return _FALLBACK

        with self._stream_lock:
            if self._stream is not None and self._stream.window_id != window.hwnd:
                self._stop_stream()
            if self._stream is None:
                stream = self.stream_class(window.hwnd, width, height)
                try:
                    started = stream.start()
                except Exception as e:
                    stream.error, started = e, False
                if not started:
                    stream.stop()
                    return self._fail(stream.error)
                self._stream = stream
                logger.info(f"ScreenCaptureKit stream started for window {window.hwnd} at {width}x{height}")
            stream = self._stream
            stream.resize(width, height)

        sample, seq = stream.latest(self._last_seq, NEW_FRAME_WAIT)
        if stream.error is not None:
            with self._stream_lock:
                return self._fail(stream.error)
        if sample is None:
            if time.time() - stream.started_at > FIRST_FRAME_TIMEOUT:
                with self._stream_lock:
                    return self._fail("no frames delivered")
            return _FALLBACK
        self._last_seq = seq

        try:
            img = self.sample_to_bgr(sample)
        except Exception as e:
            logger.error(f"ScreenCaptureKit frame conversion error: {e}")
            return _FALLBACK
        if img is None:
            return None
        # Same rule as Quartz capture: drop frames while the stream and the
        # window geometry disagree, then crop the client area off the title bar.
        if img.shape[1] != width or img.shape[0] != height:
            return None
        target_w, target_h = window.client_width, window.client_height
        if not (0 < target_w <= width and 0 < target_h <= height):
            return None
        return img[height - target_h:height, :target_w]

    @staticmethod
    def sample_to_bgr(sample_buffer):
        pixel_buffer = CoreMedia.CMSampleBufferGetImageBuffer(sample_buffer)
        if pixel_buffer is None:
            return None
        return pixel_buffer_to_bgr(pixel_buffer)
