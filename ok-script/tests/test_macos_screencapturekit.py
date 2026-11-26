import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ok.device.capture_methods import macos_screencapturekit as sck


def make_window(hwnd=7, width=1280, height=748, client_width=1280, client_height=720):
    return SimpleNamespace(hwnd=hwnd, window_width=width, window_height=height,
                           client_width=client_width, client_height=client_height)


class FakeStream:
    instances = []
    start_ok = True

    def __init__(self, window_id, width, height):
        self.window_id = window_id
        self.size = (width, height)
        self.error = None
        self.started_at = 0.0
        self.stopped = False
        self.sample = None
        self.seq = 0
        FakeStream.instances.append(self)

    def start(self):
        if not FakeStream.start_ok:
            self.error = "user declined"
            return False
        self.started_at = sck.time.time()
        return True

    def resize(self, width, height):
        self.size = (width, height)

    def stop(self):
        self.stopped = True

    def latest(self, after_seq, timeout):
        return self.sample, self.seq

    def push(self, frame):
        self.sample = frame
        self.seq += 1


@pytest.fixture
def method():
    FakeStream.instances = []
    FakeStream.start_ok = True
    capture = sck.MacOSScreenCaptureKitMethod(make_window())
    capture.stream_class = FakeStream
    capture.sample_to_bgr = lambda sample: sample
    with patch.object(sck.MacOSQuartzCaptureMethod, "do_get_frame", return_value="quartz"):
        yield capture


def bgr(height, width):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[height - 720:, :, 1] = 255  # client area below a 28-pixel title bar
    return frame


def test_returns_the_streamed_client_area(method):
    assert method.do_get_frame() == "quartz"  # stream started, no frame yet
    stream = FakeStream.instances[0]
    stream.push(bgr(748, 1280))
    frame = method.do_get_frame()
    assert frame.shape == (720, 1280, 3)
    assert (frame[:, :, 1] == 255).all()


def test_uses_quartz_while_geometry_disagrees(method):
    # A None frame makes the task executor sleep for a second.
    method.do_get_frame()
    FakeStream.instances[0].push(bgr(400, 700))
    assert method.do_get_frame() == "quartz"


def test_resizes_the_stream_with_the_window(method):
    method.do_get_frame()
    method.hwnd_window.window_width, method.hwnd_window.window_height = 1920, 1108
    method.do_get_frame()
    assert FakeStream.instances[0].size == (1920, 1108)
    assert len(FakeStream.instances) == 1


def test_restarts_the_stream_for_a_new_window(method):
    method.do_get_frame()
    method.hwnd_window.hwnd = 9
    method.do_get_frame()
    assert FakeStream.instances[0].stopped
    assert FakeStream.instances[1].window_id == 9


def test_falls_back_to_quartz_and_retries_later_when_start_fails(method):
    FakeStream.start_ok = False
    assert method.do_get_frame() == "quartz"
    assert method.do_get_frame() == "quartz"
    assert len(FakeStream.instances) == 1  # waits RETRY_AFTER before trying again
    with patch.object(sck.time, "time", return_value=sck.time.time() + sck.RETRY_AFTER + 1):
        FakeStream.start_ok = True
        method.do_get_frame()
    assert len(FakeStream.instances) == 2


def test_falls_back_when_the_system_stops_the_stream(method):
    method.do_get_frame()
    stream = FakeStream.instances[0]
    stream.push(bgr(748, 1280))
    stream.error = "system stopped stream"
    assert method.do_get_frame() == "quartz"
    assert stream.stopped


def test_falls_back_when_no_frames_arrive(method):
    method.do_get_frame()
    FakeStream.instances[0].started_at -= sck.FIRST_FRAME_TIMEOUT + 1
    assert method.do_get_frame() == "quartz"
    assert FakeStream.instances[0].stopped


def test_close_stops_the_stream(method):
    method.do_get_frame()
    method.close()
    assert FakeStream.instances[0].stopped


def test_quartz_env_override_disables_screencapturekit(monkeypatch):
    kit = MagicMock()
    kit.SCStreamConfiguration.instancesRespondToSelector_.return_value = True
    with patch.multiple(sck, ScreenCaptureKit=kit, CoreMedia=MagicMock(), Quartz=MagicMock()):
        assert sck.available()
        monkeypatch.setenv("OK_MAC_CAPTURE", "quartz")
        assert not sck.available()


def test_unavailable_before_macos_14_or_without_bindings():
    kit = MagicMock()
    kit.SCStreamConfiguration.instancesRespondToSelector_.return_value = False
    with patch.multiple(sck, ScreenCaptureKit=kit, CoreMedia=MagicMock(), Quartz=MagicMock()):
        assert not sck.available()
    with patch.object(sck, "ScreenCaptureKit", None):
        assert not sck.available()


def test_capture_class_selection():
    from ok.device.capture_methods import update
    from ok.device.capture_methods.macos_quartz import MacOSQuartzCaptureMethod
    with patch.object(sck, "available", return_value=True):
        assert update.macos_capture_class() is sck.MacOSScreenCaptureKitMethod
    with patch.object(sck, "available", return_value=False):
        assert update.macos_capture_class() is MacOSQuartzCaptureMethod


def test_pixel_buffer_conversion_drops_row_padding_and_alpha():
    height, width, bytes_per_row = 3, 4, 32  # 4 pixels of padding per row
    raw = np.arange(height * bytes_per_row, dtype=np.uint8)
    quartz = MagicMock()
    quartz.CVPixelBufferGetWidth.return_value = width
    quartz.CVPixelBufferGetHeight.return_value = height
    quartz.CVPixelBufferGetBytesPerRow.return_value = bytes_per_row
    quartz.CVPixelBufferGetBaseAddress.return_value = SimpleNamespace(as_buffer=lambda size: raw[:size].tobytes())
    with patch.object(sck, "Quartz", quartz):
        frame = sck.pixel_buffer_to_bgr("buffer")
    expected = raw.reshape(height, bytes_per_row // 4, 4)[:, :width, :3]
    assert frame.shape == (height, width, 3)
    assert (frame == expected).all()
    quartz.CVPixelBufferUnlockBaseAddress.assert_called_once()


def test_window_stream_keeps_only_complete_frames():
    kit = MagicMock(SCStreamFrameInfoStatus="status", SCFrameStatusComplete=0)
    media = MagicMock()
    stream = sck.WindowStream(7, 1280, 748)
    with patch.multiple(sck, ScreenCaptureKit=kit, CoreMedia=media):
        media.CMSampleBufferGetSampleAttachmentsArray.return_value = [{"status": 1}]  # idle
        stream.on_sample("idle")
        assert stream.latest(0, 0) == (None, 0)
        media.CMSampleBufferGetSampleAttachmentsArray.return_value = [{"status": 0}]
        stream.on_sample("complete")
        assert stream.latest(0, 0) == ("complete", 1)


def test_window_stream_wait_wakes_on_a_new_frame():
    kit = MagicMock(SCStreamFrameInfoStatus="status", SCFrameStatusComplete=0)
    media = MagicMock()
    media.CMSampleBufferGetSampleAttachmentsArray.return_value = [{"status": 0}]
    stream = sck.WindowStream(7, 1280, 748)
    with patch.multiple(sck, ScreenCaptureKit=kit, CoreMedia=media):
        timer = threading.Timer(0.01, stream.on_sample, args=("frame",))
        timer.start()
        sample, seq = stream.latest(0, 5)
        timer.join()
    assert (sample, seq) == ("frame", 1)


# These run against the real pyobjc bindings on the macOS CI runner. The
# runner has no Screen Recording permission, so they check that the calls are
# well-formed and that failure is reported instead of hanging, not capture itself.
needs_sck = pytest.mark.skipif(not sck.available(), reason="needs ScreenCaptureKit on macOS 14+")


@needs_sck
def test_real_bindings_build_a_stream_configuration():
    config = sck.WindowStream._configuration(1280, 748)
    assert (config.width(), config.height()) == (1280, 748)
    assert config.pixelFormat() == sck.Quartz.kCVPixelFormatType_32BGRA
    assert not config.showsCursor()
    assert sck._output_class() is sck._output_class()


@needs_sck
def test_real_bindings_report_an_unknown_window_without_hanging():
    stream = sck.WindowStream(0x7FFFFFF0, 1280, 748)
    started_at = sck.time.time()
    assert not stream.start()
    assert stream.error is not None
    assert sck.time.time() - started_at < sck.START_TIMEOUT + 1
    stream.stop()
