"""macOS window discovery, geometry, and control utilities using Quartz and AppKit."""

from __future__ import annotations

import os
import re
import subprocess
import time
from typing import List, Optional, Tuple

import psutil

from ok.util.logger import Logger

logger = Logger.get_logger("capture")


def _quartz():
    import Quartz
    return Quartz


def _appkit():
    import AppKit
    return AppKit


def is_blank(image):
    return image is None or not image.any()


def windows_graphics_available():
    """On macOS, Quartz window capture (CGWindowListCreateImage) is always available."""
    return True


def _get_window_dict(hwnd: int) -> Optional[dict]:
    if not hwnd or hwnd <= 0:
        return None
    try:
        Quartz = _quartz()
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionIncludingWindow, int(hwnd)
        )
        if window_list and len(window_list) > 0:
            return window_list[0]
        # Fallback: search all windows in case window is off-screen or minimized
        all_windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
        )
        if all_windows:
            for w in all_windows:
                if int(w.get(Quartz.kCGWindowNumber, 0)) == int(hwnd):
                    return w
    except Exception as e:
        logger.debug(f"_get_window_dict error for {hwnd}: {e}")
    return None


def is_window_valid(hwnd: int) -> bool:
    return _get_window_dict(hwnd) is not None


def is_window_minimized(hwnd: int) -> bool:
    info = _get_window_dict(hwnd)
    if not info:
        return True
    Quartz = _quartz()
    return not bool(info.get(Quartz.kCGWindowIsOnscreen, False))


def get_window_title(hwnd: int) -> str:
    info = _get_window_dict(hwnd)
    if not info:
        return ""
    Quartz = _quartz()
    title = info.get(Quartz.kCGWindowName) or info.get(Quartz.kCGWindowOwnerName) or ""
    return str(title)


def get_window_class_name(hwnd: int) -> str:
    info = _get_window_dict(hwnd)
    if not info:
        return ""
    Quartz = _quartz()
    return str(info.get(Quartz.kCGWindowOwnerName) or "")


def get_window_pid(hwnd: int) -> int:
    info = _get_window_dict(hwnd)
    if not info:
        return 0
    Quartz = _quartz()
    return int(info.get(Quartz.kCGWindowOwnerPID, 0))


def get_exe_by_hwnd(hwnd: int) -> Tuple[str, str, List[str]]:
    try:
        pid = get_window_pid(hwnd)
        if pid <= 0:
            return "", "", []
        proc = psutil.Process(pid)
        try:
            name = proc.name()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            name = ""
        try:
            exe = proc.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            exe = ""
        try:
            cmdline = proc.cmdline()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            cmdline = []
        return name, exe, cmdline
    except Exception as e:
        logger.debug(f"get_exe_by_hwnd error: {e}")
        return "", "", []


_window_metrics_cache = {}


def _detect_title_bar_pixels_from_cgimage(cg_img, scaling: float) -> int:
    """Detect the exact macOS title bar height in physical pixels from a window CGImage."""
    try:
        import numpy as np
        Quartz = _quartz()
        px_w = Quartz.CGImageGetWidth(cg_img)
        px_h = Quartz.CGImageGetHeight(cg_img)
        bpr = Quartz.CGImageGetBytesPerRow(cg_img)
        max_scan = min(px_h, int(round(45 * scaling)))
        if px_w < 100 or max_scan < int(round(22 * scaling)) or bpr < px_w * 4:
            return 0
        provider = Quartz.CGImageGetDataProvider(cg_img)
        if provider is None:
            return 0
        buf = Quartz.CGDataProviderCopyData(provider)
        if buf is None:
            return 0
        arr = np.frombuffer(buf, dtype=np.uint8, count=max_scan * bpr).reshape((max_scan, bpr // 4, 4))[:, :px_w, :]
        # Standard titled macOS windows have rounded top corners with alpha == 0 at (0, 0) and (0, px_w - 1)
        if int(arr[0, 0, 3]) != 0 and int(arr[0, px_w - 1, 3]) != 0:
            return 0
        x1, x2 = int(px_w * 0.50), int(px_w * 0.85)
        ref_row = int(round(10 * scaling))
        ref_strip = arr[ref_row, x1:x2, :3].astype(np.int16)
        # Verify the reference row inside the title bar is a uniform solid color
        if int((ref_strip.max(axis=0) - ref_strip.min(axis=0)).max()) > 4:
            return 0
        min_title_px = int(round(20 * scaling))
        max_title_px = int(round(42 * scaling))
        for r in range(min_title_px, min(max_scan, max_title_px + 1)):
            row_strip = arr[r, x1:x2, :3].astype(np.int16)
            diff = int(np.abs(row_strip - ref_strip).max())
            if diff > 5:
                return r
    except Exception as e:
        logger.debug(f"_detect_title_bar_pixels_from_cgimage error: {e}")
    return 0


def _estimate_title_bar_points(logical_w: int, logical_h: int) -> int:
    """Fallback heuristic for macOS title bar height in logical points."""
    if logical_w <= 0 or logical_h <= 0:
        return 0
    for target_ratio in (16.0 / 9.0, 21.0 / 9.0, 16.0 / 10.0, 1512.0 / 982.0, 4.0 / 3.0):
        expected_h = int(round(logical_w / target_ratio))
        diff = logical_h - expected_h
        if 20 <= diff <= 42:
            return diff
    return 0


def _get_window_scale_and_title_bar(x: float, y: float, logical_w: int, logical_h: int, hwnd: int = 0) -> Tuple[float, int]:
    """Cache title detection only after checking the current backing image size."""

    scaling = 2.0
    title_pt = 0
    if hwnd > 0 and logical_w > 0 and logical_h > 0:
        try:
            Quartz = _quartz()
            cg_img = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                int(hwnd),
                Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageBestResolution,
            )
            if cg_img is not None:
                px_w = Quartz.CGImageGetWidth(cg_img)
                px_h = Quartz.CGImageGetHeight(cg_img)
                cache_key = (int(hwnd), x, y, logical_w, logical_h, px_w, px_h)
                if cache_key in _window_metrics_cache:
                    return _window_metrics_cache[cache_key]
                if px_w > 0:
                    scale = round(px_w / float(logical_w), 2)
                    if scale >= 1.0:
                        scaling = scale
                    title_px = _detect_title_bar_pixels_from_cgimage(cg_img, scaling)
                    if title_px > 0:
                        title_pt = int(round(title_px / scaling))
                    else:
                        title_pt = _estimate_title_bar_points(logical_w, logical_h)
                    if len(_window_metrics_cache) > 64:
                        _window_metrics_cache.clear()
                    _window_metrics_cache[cache_key] = (scaling, title_pt)
                    return scaling, title_pt
        except Exception:
            pass

    try:
        AppKit = _appkit()
        for screen in AppKit.NSScreen.screens():
            frame = screen.frame()
            if (frame.origin.x <= x + logical_w / 2 <= frame.origin.x + frame.size.width):
                scaling = float(screen.backingScaleFactor())
                break
        else:
            main_screen = AppKit.NSScreen.mainScreen()
            if main_screen is not None:
                scaling = float(main_screen.backingScaleFactor())
    except Exception:
        pass
    title_pt = _estimate_title_bar_points(logical_w, logical_h)
    return scaling, title_pt


def get_window_bounds(hwnd: int):
    """Return (client_x, client_y, window_width, window_height, client_width, client_height, scaling).

    Note:
    - client_x, client_y are returned in logical screen points (for mouse placement).
    - window_width, window_height, client_width, client_height are returned in physical backing pixels
      so that resolution checks (>= 1280x720) and template matching match the captured CGImage.
    - scaling is the Retina backing scale factor (e.g., 2.0 on Retina displays).
    """
    try:
        info = _get_window_dict(hwnd)
        if not info:
            return 0, 0, 0, 0, 0, 0, 1.0
        Quartz = _quartz()
        bounds = info.get(Quartz.kCGWindowBounds, {})
        logical_x = int(round(float(bounds.get("X", 0))))
        logical_y = int(round(float(bounds.get("Y", 0))))
        logical_w = int(round(float(bounds.get("Width", 0))))
        logical_h = int(round(float(bounds.get("Height", 0))))
        if logical_w <= 0 or logical_h <= 0:
            return 0, 0, 0, 0, 0, 0, 1.0

        scaling, title_pt = _get_window_scale_and_title_bar(logical_x, logical_y, logical_w, logical_h, hwnd=hwnd)

        client_x = logical_x
        client_y = logical_y + title_pt
        logical_client_w = logical_w
        logical_client_h = logical_h - title_pt

        window_width = int(round(logical_w * scaling))
        window_height = int(round(logical_h * scaling))
        client_width = int(round(logical_client_w * scaling))
        client_height = int(round(logical_client_h * scaling))

        return client_x, client_y, window_width, window_height, client_width, client_height, scaling
    except Exception as e:
        logger.error("get_window_bounds exception", e)
        return 0, 0, 0, 0, 0, 0, 1.0


def is_foreground_window(hwnd: int) -> bool:
    if not hwnd or hwnd <= 0:
        return False
    try:
        pid = get_window_pid(hwnd)
        if pid <= 0:
            return False
        # Query the frontmost window on screen via Quartz (safe from background threads)
        Quartz = _quartz()
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        if window_list:
            for w in window_list:
                layer = int(w.get(Quartz.kCGWindowLayer, 0))
                if layer != 0:
                    continue
                owner_pid = int(w.get(Quartz.kCGWindowOwnerPID, 0))
                w_id = int(w.get(Quartz.kCGWindowNumber, 0))
                return owner_pid == pid or w_id == int(hwnd)
    except Exception as e:
        logger.debug(f"is_foreground_window error: {e}")
    return False


def bring_window_to_front(hwnd: int) -> bool:
    if not hwnd or hwnd <= 0:
        return False
    try:
        pid = get_window_pid(hwnd)
        if pid <= 0:
            return False
        AppKit = _appkit()
        app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is not None:
            return bool(app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps))
    except Exception as e:
        logger.warning(f"bring_window_to_front failed for {hwnd}: {e}")
    return False


def show_title_bar(hwnd: int) -> bool:
    return True


def resize_window(hwnd: int, width: int, height: int) -> bool:
    """Resize and center a macOS window given target dimensions in physical pixels."""
    if not hwnd or hwnd <= 0:
        return False
    try:
        pid = get_window_pid(hwnd)
        if pid <= 0:
            return False
        _, _, _, _, _, _, scaling = get_window_bounds(hwnd)
        scaling = scaling or 1.0
        target_logical_w = int(round(width / scaling))
        target_logical_h = int(round(height / scaling))

        Quartz = _quartz()
        main_display = Quartz.CGMainDisplayID()
        bounds = Quartz.CGDisplayBounds(main_display)
        screen_w = int(bounds.size.width)
        screen_h = int(bounds.size.height)
        center_x = max(0, (screen_w - target_logical_w) // 2)
        center_y = max(25, (screen_h - target_logical_h) // 2)

        script = (
            f'tell application "System Events"\n'
            f'  tell (first process whose unix id is {pid})\n'
            f'    if (count of windows) > 0 then\n'
            f'      set size of window 1 to {{{target_logical_w}, {target_logical_h}}}\n'
            f'      set position of window 1 to {{{center_x}, {center_y}}}\n'
            f'    end if\n'
            f'  end tell\n'
            f'end tell'
        )
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
        time.sleep(0.3)
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Error resizing macOS window {hwnd}: {e}")
        return False


def get_monitors_bounds() -> List[Tuple[int, int, int, int]]:
    bounds_list = []
    try:
        Quartz = _quartz()
        err, ids, count = Quartz.CGGetActiveDisplayList(16, None, None)
        if err == 0 and ids:
            for d_id in ids[:count]:
                rect = Quartz.CGDisplayBounds(d_id)
                left = int(rect.origin.x)
                top = int(rect.origin.y)
                right = int(rect.origin.x + rect.size.width)
                bottom = int(rect.origin.y + rect.size.height)
                bounds_list.append((left, top, right, bottom))
    except Exception as e:
        logger.debug(f"get_monitors_bounds error: {e}")
    if not bounds_list:
        bounds_list.append((0, 0, 3840, 2160))
    return bounds_list


def compare_path_safe(str1, str2):
    if str1 is None and str2 is None:
        return True
    if str1 is None or str2 is None:
        return False
    s1 = str1.replace('\\', '/').lower()
    s2 = str2.replace('\\', '/').lower()
    if s1 == s2:
        return True
    # Also allow matching without .exe suffix on macOS (e.g. Client-Win64-Shipping.exe vs Client-Mac-Shipping)
    base1 = os.path.basename(s1)
    base2 = os.path.basename(s2)
    return base1 == base2


def _match_exe_name(proc_name: str, full_path: str, owner_name: str, exe_names: List[str]) -> bool:
    if not exe_names:
        return True
    candidates = [proc_name, full_path, owner_name]
    if full_path:
        candidates.append(os.path.basename(full_path))
        # Check .app bundle name if inside Foo.app/Contents/MacOS/...
        parts = full_path.split("/")
        for p in parts:
            if p.lower().endswith(".app"):
                candidates.append(p)
                candidates.append(p[:-4])

    for exe_name in exe_names:
        if not exe_name:
            continue
        exe_clean = exe_name.lower()
        exe_no_ext = exe_clean[:-4] if exe_clean.endswith(".exe") else exe_clean
        # Map Windows Wuthering Waves binary name to macOS binary name automatically
        mapped_names = {exe_clean, exe_no_ext}
        if "client-win64-shipping" in exe_clean or "wuthering waves" in exe_clean:
            mapped_names.update({"client-mac-shipping", "wutheringwaves", "wuthering waves", "wuthering waves.app"})
        for cand in candidates:
            if not cand:
                continue
            cand_low = cand.lower()
            if cand_low in mapped_names or any(compare_path_safe(cand_low, m) for m in mapped_names):
                return True
    return False


def find_hwnd(title, exe_names, frame_width, frame_height, player_id=-1, class_name=None,
              selected_hwnd=0, top_hwnd_class=None, last_hwnd=0):
    if exe_names is None and title is None:
        return None, 0, None, 0, 0, 0, 0, []
    if isinstance(exe_names, str):
        exe_names = [exe_names]

    results = []
    try:
        Quartz = _quartz()
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        if not window_list:
            window_list = []

        for w in window_list:
            layer = int(w.get(Quartz.kCGWindowLayer, 0))
            if layer != 0:
                continue
            hwnd = int(w.get(Quartz.kCGWindowNumber, 0))
            if hwnd <= 0:
                continue
            owner_name = str(w.get(Quartz.kCGWindowOwnerName) or "")
            win_name = str(w.get(Quartz.kCGWindowName) or owner_name)
            bounds = w.get(Quartz.kCGWindowBounds, {})
            bw = int(round(float(bounds.get("Width", 0))))
            bh = int(round(float(bounds.get("Height", 0))))
            if bw < 640 or bh < 360:
                continue

            if title:
                if isinstance(title, str):
                    if title.lower() not in win_name.lower() and title.lower() not in owner_name.lower():
                        continue
                elif not (re.search(title, win_name) or re.search(title, owner_name)):
                    continue

            proc_name, full_path, _ = get_exe_by_hwnd(hwnd)
            if exe_names and not _match_exe_name(proc_name, full_path, owner_name, exe_names):
                continue

            x, y, win_w, win_h, width, height, m_scaling = get_window_bounds(hwnd)
            if width <= 10 or height <= 10:
                continue

            results.append((hwnd, full_path, width, height, x, y, win_name, owner_name, m_scaling))
    except Exception as e:
        logger.error(f"find_hwnd macOS error: {e}")

    if not results:
        return None, 0, None, 0, 0, 0, 0, []

    w_biggest = max(results, key=lambda r: r[2] * r[3])
    w_selected = next((r for r in results if 0 < selected_hwnd == r[0]), None)
    w_last = next((r for r in results if 0 < last_hwnd == r[0]), None)

    biggest = w_biggest
    if w_selected:
        biggest = w_selected
    elif w_last and w_biggest:
        if (w_biggest[2] * w_biggest[3]) <= (w_last[2] * w_last[3]) * 1.1:
            biggest = w_last

    results = [biggest]

    # Calculate pixel offset if window has a title bar
    info = _get_window_dict(biggest[0])
    x_offset, y_offset = 0, 0
    if info:
        Quartz = _quartz()
        bounds = info.get(Quartz.kCGWindowBounds, {})
        logical_x = int(round(float(bounds.get("X", 0))))
        logical_y = int(round(float(bounds.get("Y", 0))))
        logical_w = int(round(float(bounds.get("Width", 0))))
        logical_h = int(round(float(bounds.get("Height", 0))))
        scaling, title_pt = _get_window_scale_and_title_bar(logical_x, logical_y, logical_w, logical_h, hwnd=biggest[0])
        if title_pt > 0:
            y_offset = int(round(title_pt * scaling))

    real_width, real_height = biggest[2], biggest[3]
    return biggest[6], biggest[0], biggest[1], x_offset, y_offset, real_width, real_height, results


def find_all_visible_windows():
    windows = []
    try:
        Quartz = _quartz()
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        if not window_list:
            return windows
        for w in window_list:
            if int(w.get(Quartz.kCGWindowLayer, 0)) != 0:
                continue
            hwnd = int(w.get(Quartz.kCGWindowNumber, 0))
            owner_name = str(w.get(Quartz.kCGWindowOwnerName) or "")
            title = str(w.get(Quartz.kCGWindowName) or owner_name).strip()
            if not title:
                continue
            bounds = w.get(Quartz.kCGWindowBounds, {})
            if float(bounds.get("Width", 0)) <= 50 or float(bounds.get("Height", 0)) <= 50:
                continue
            proc_name, full_path, _ = get_exe_by_hwnd(hwnd)
            windows.append((hwnd, title, proc_name or owner_name, full_path))
    except Exception as e:
        logger.debug(f"find_all_visible_windows error: {e}")
    return windows
