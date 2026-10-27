import sys
import time

if sys.platform == "win32":
    import win32api
    import win32con
    import win32gui
else:
    win32api = None
    win32con = None
    win32gui = None

from ok.device.capture_methods.base import BaseCaptureMethod
from ok.device.interaction_methods.base import BaseInteraction
from ok.device.interaction_methods.keys import vk_key_dict
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

if sys.platform != "win32":
    from ok.device.interaction_methods.macos_quartz import MacOSQuartzInteraction


    class PostMessageInteraction(MacOSQuartzInteraction):
        def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01, move=True, key="left"):
            if hasattr(self, 'post') and callable(getattr(self, 'post')):
                w_con = sys.modules.get('win32con')
                btn_down = getattr(w_con, 'WM_LBUTTONDOWN', 0x0201) if key == "left" else 0
                btn_up = getattr(w_con, 'WM_LBUTTONUP', 0x0202) if key == "left" else 0
                long_pos = self.update_mouse_pos(x, y) if hasattr(self, 'update_mouse_pos') else 0
                self.post(btn_down, 1, long_pos)
                time.sleep(down_time)
                self.post(btn_up, 0, long_pos)
                return
            super().click(x, y, move_back=move_back, name=name, down_time=down_time, move=move, key=key)
else:
    class PostMessageInteraction(BaseInteraction):

        def __init__(self, capture: BaseCaptureMethod, hwnd_window):
            super().__init__(capture)
            self.hwnd_window = hwnd_window
            self.mouse_pos = (0, 0)
            self.lparam = 0x1e0001
            self._dynamic_target_hwnd = 0

        @property
        def hwnd(self):
            if self._dynamic_target_hwnd != 0:
                if win32gui.IsWindow(self._dynamic_target_hwnd):
                    return self._dynamic_target_hwnd
            return self.hwnd_window.top_hwnd if self.hwnd_window.top_hwnd else self.hwnd_window.hwnd

        def send_key(self, key, down_time=0.01):
            super().send_key(key, down_time)
            self.send_key_down(key)
            time.sleep(down_time)
            self.send_key_up(key)

        def send_key_down(self, key, activate=True):
            if activate:
                self.try_activate()
            vk_code = self.get_key_by_str(key)
            lparam = self.make_lparam(vk_code, is_up=False)
            self.post(win32con.WM_KEYDOWN, vk_code, lparam)

        def send_key_up(self, key):
            # logger.debug(f'send_key_up {key}')
            vk_code = self.get_key_by_str(key)
            lparam = self.make_lparam(vk_code, is_up=True)
            self.post(win32con.WM_KEYUP, vk_code, lparam)

        def make_lparam(self, vk_code, is_up=False):
            scan_code = win32api.MapVirtualKey(vk_code, 0)
            lparam = (scan_code << 16) | 1
            if is_up:
                lparam |= (1 << 30) | (1 << 31)
            return lparam

        def get_key_by_str(self, key):
            key = str(key)
            if key_code := vk_key_dict.get(key.upper()):
                vk_code = key_code
            else:
                vk_code = win32api.VkKeyScan(key)
            return vk_code

        def input_text(self, text, activate=True):
            if activate:
                self.try_activate()
            for c in text:
                self.post(win32con.WM_CHAR,
                          ord(c), 0)
                time.sleep(0.01)

        def move(self, x, y, down_btn=0):
            long_pos = self.update_mouse_pos(x, y, True)
            self.post(win32con.WM_MOUSEMOVE, down_btn, long_pos)
            return long_pos

        def scroll(self, x, y, scroll_amount):
            self.try_activate()
            logger.debug(f'scroll {x}, {y}, {scroll_amount}')
            if x > 0 and y > 0:
                long_position = self.update_mouse_pos(x, y)
            else:
                long_position = 0
            wParam = win32api.MAKELONG(0, win32con.WHEEL_DELTA * scroll_amount)
            self.post(win32con.WM_MOUSEWHEEL, wParam, long_position)

        def post(self, message, wParam=0, lParam=0, hwnd=None):
            if hwnd is None:
                hwnd = self.hwnd
            try:
                win32gui.PostMessage(hwnd, message, wParam, lParam)
            except Exception as e:
                logger.error(f'PostMessage error {hwnd}: {e}')

        def swipe(self, x1, y1, x2, y2, duration=3, settle_time=0):
            self.move(x1, y1)
            time.sleep(0.1)
            self.mouse_down(x1, y1)
            dx = x2 - x1
            dy = y2 - y1
            steps = int(duration / 100)
            step_dx = dx / steps
            step_dy = dy / steps
            for i in range(steps):
                self.move(x1 + int(i * step_dx), y1 + int(i * step_dy), down_btn=win32con.MK_LBUTTON)
                time.sleep(0.01)
            self.mouse_up()

        def activate(self, hwnd=None):
            self.post(win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0, hwnd=hwnd)

        def deactivate(self, hwnd=None):
            self.post(win32con.WM_ACTIVATE, win32con.WA_INACTIVE, 0, hwnd=hwnd)

        def try_activate(self):
            base_hwnd = self.hwnd_window.hwnd
            current_hwnd = self.hwnd

            self.activate(base_hwnd)
            if current_hwnd != base_hwnd:
                self.activate(current_hwnd)

        def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01, move=True, key="left"):
            super().click(x, y, name=name)
            if move:
                long_position = self.move(x, y)
                time.sleep(down_time)
            else:
                long_position = self.update_mouse_pos(x, y, activate=True)

            if key == "left":
                btn_down = win32con.WM_LBUTTONDOWN
                btn_mk = win32con.MK_LBUTTON
                btn_up = win32con.WM_LBUTTONUP
            elif key == "middle":
                btn_down = win32con.WM_MBUTTONDOWN
                btn_mk = win32con.MK_MBUTTON
                btn_up = win32con.WM_MBUTTONUP
            else:
                btn_down = win32con.WM_RBUTTONDOWN
                btn_mk = win32con.MK_RBUTTON
                btn_up = win32con.WM_RBUTTONUP

            self.post(btn_down, btn_mk, long_position)
            time.sleep(down_time)
            self.post(btn_up, 0, long_position)

        def right_click(self, x=-1, y=-1, move_back=False, name=None):
            super().right_click(x, y, name=name)
            long_position = self.update_mouse_pos(x, y)
            self.post(win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, long_position)
            self.post(win32con.WM_RBUTTONUP, 0, long_position)

        def mouse_down(self, x=-1, y=-1, name=None, key="left"):
            long_position = self.update_mouse_pos(x, y)
            if key == "left":
                action = win32con.WM_LBUTTONDOWN
                btn = win32con.MK_LBUTTON
            elif key == "middle":
                action = win32con.WM_MBUTTONDOWN
                btn = win32con.MK_MBUTTON
            else:
                action = win32con.WM_RBUTTONDOWN
                btn = win32con.MK_RBUTTON
            self.post(action, btn, long_position)

        def update_mouse_pos(self, x, y, activate=True):
            self.try_activate()

            base_hwnd = self.hwnd_window.top_hwnd if self.hwnd_window.top_hwnd else self.hwnd_window.hwnd

            if x == -1 or y == -1:
                x, y = getattr(self, 'bg_mouse_pos', (0, 0))
            else:
                x, y = self.hwnd_window.get_top_window_cords(x, y)
                self.bg_mouse_pos = (x, y)

            try:
                abs_x, abs_y = win32gui.ClientToScreen(base_hwnd, (int(x), int(y)))

                target_hwnd = base_hwnd
                hwnds = getattr(self.hwnd_window, 'hwnds', [])
                for hwnd_info in hwnds:
                    candidate = hwnd_info[0]
                    if not win32gui.IsWindow(candidate):
                        continue
                    try:
                        left = hwnd_info[4]
                        top = hwnd_info[5]
                        right = left + hwnd_info[2]
                        bottom = top + hwnd_info[3]
                        if left <= abs_x < right and top <= abs_y < bottom:
                            target_hwnd = candidate
                            break
                    except Exception:
                        continue
                self._dynamic_target_hwnd = target_hwnd

                local_x, local_y = win32gui.ScreenToClient(target_hwnd, (abs_x, abs_y))

                return win32api.MAKELONG(local_x, local_y)

            except Exception as e:
                logger.error(f'update_mouse_pos conversion error targeting {base_hwnd}', e)
                self._dynamic_target_hwnd = base_hwnd
                return win32api.MAKELONG(int(x), int(y))

        def mouse_up(self, key="left"):
            if key == "left":
                action = win32con.WM_LBUTTONUP
            elif key == "middle":
                action = win32con.WM_MBUTTONUP
            else:
                action = win32con.WM_RBUTTONUP
            self.post(action, 0,
                      win32api.MAKELONG(self.mouse_pos[0], self.mouse_pos[1]))

        def should_capture(self):
            return True
