import threading
import time
import numpy as np

from ok.device.capture_methods.base import BaseWindowsCaptureMethod
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

try:
    import Quartz
except Exception as e:
    Quartz = None
    logger.warning(f"Failed to import Quartz in macos_quartz: {e}")


class MacOSQuartzCaptureMethod(BaseWindowsCaptureMethod):
    name = "macOS Quartz Window Capture"
    short_description = "native macOS CGWindowListCreateImage"
    description = (
        "\nCaptures the game window directly using macOS CoreGraphics (Quartz). "
        "\nSupports background/occluded windows and Retina displays."
    )

    def __init__(self, hwnd_window):
        super().__init__(hwnd_window)
        self.lock = threading.Lock()
        self._warned_permission = False
        self.exit_event = getattr(hwnd_window, "app_exit_event", None)

    def do_get_frame(self):
        if Quartz is None or self.hwnd_window is None:
            return None

        hwnd = self.hwnd_window.hwnd
        if hwnd <= 0:
            return None

        with self.lock:
            try:
                image_options = (
                    Quartz.kCGWindowImageBoundsIgnoreFraming
                    | Quartz.kCGWindowImageBestResolution
                )
                cg_img = Quartz.CGWindowListCreateImage(
                    Quartz.CGRectNull,
                    Quartz.kCGWindowListOptionIncludingWindow,
                    hwnd,
                    image_options,
                )
                if cg_img is None:
                    if not self._warned_permission:
                        self._warned_permission = True
                        logger.warning(
                            "CGWindowListCreateImage returned None. Ensure Screen Recording permission is granted in System Settings -> Privacy & Security -> Screen & System Audio Recording."
                        )
                    return None

                width = Quartz.CGImageGetWidth(cg_img)
                height = Quartz.CGImageGetHeight(cg_img)
                if width <= 10 or height <= 10:
                    return None

                bytes_per_row = Quartz.CGImageGetBytesPerRow(cg_img)
                provider = Quartz.CGImageGetDataProvider(cg_img)
                if provider is None:
                    return None
                data = Quartz.CGDataProviderCopyData(provider)
                if data is None:
                    return None

                buf = np.frombuffer(data, dtype=np.uint8)
                row_pixels = bytes_per_row // 4
                if buf.size < height * bytes_per_row:
                    return None

                img = buf[: height * bytes_per_row].reshape((height, row_pixels, 4))
                img = img[:, :width, :3].copy()

                # Window discovery and capture run on separate threads. During
                # animations, discard frames until backing geometry agrees;
                # never crop a new frame to a stale miniature discovery size.
                expected_w = self.hwnd_window.window_width
                expected_h = self.hwnd_window.window_height
                if (width, height) != (expected_w, expected_h):
                    return None
                target_w = self.hwnd_window.client_width
                target_h = self.hwnd_window.client_height
                if not (0 < target_w <= width and 0 < target_h <= height):
                    return None
                img = img[height - target_h:height, :target_w]

                return img
            except Exception as e:
                logger.error(f"MacOSQuartzCaptureMethod.do_get_frame error: {e}")
                return None

    def get_frame_for_probe(self, timeout=1.0):
        return self.do_get_frame()

    def start_or_stop(self):
        return self.connected()
