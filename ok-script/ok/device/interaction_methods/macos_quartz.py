import time

from ok.device.capture_methods.base import BaseCaptureMethod
from ok.device.interaction_methods.base import BaseInteraction
from ok.util.logger import Logger
from ok.task.exceptions import TaskDisabledException
from ok.util.window_macos import get_window_pid

logger = Logger.get_logger(__name__)

try:
    import Quartz
except Exception as e:
    Quartz = None
    logger.warning(f"Failed to import Quartz in macos_quartz interaction: {e}")

# macOS virtual keycodes (kVK_ANSI_* and kVK_*)
MAC_KEYCODE_MAP = {
    'a': 0x00, 's': 0x01, 'd': 0x02, 'f': 0x03, 'h': 0x04, 'g': 0x05, 'z': 0x06, 'x': 0x07,
    'c': 0x08, 'v': 0x09, 'b': 0x0B, 'q': 0x0C, 'w': 0x0D, 'e': 0x0E, 'r': 0x0F, 'y': 0x10,
    't': 0x11, '1': 0x12, '2': 0x13, '3': 0x14, '4': 0x15, '6': 0x16, '5': 0x17, '=': 0x18,
    '9': 0x19, '7': 0x1A, '-': 0x1B, '8': 0x1C, '0': 0x1D, ']': 0x1E, 'o': 0x1F, 'u': 0x20,
    '[': 0x21, 'i': 0x22, 'p': 0x23, 'l': 0x25, 'j': 0x26, "'": 0x27, 'k': 0x28, ';': 0x29,
    '\\': 0x2A, ',': 0x2B, '/': 0x2C, 'n': 0x2D, 'm': 0x2E, '.': 0x2F, '`': 0x32,
    'return': 0x24, 'enter': 0x24, 'tab': 0x30, 'space': 0x31, 'backspace': 0x33,
    'esc': 0x35, 'escape': 0x35,
    'cmd': 0x37, 'command': 0x37, 'win': 0x37, 'windows': 0x37, 'meta': 0x37, 'cmd_l': 0x37, 'cmd_r': 0x36,
    'shift': 0x38, 'lshift': 0x38, 'shift_l': 0x38, 'rshift': 0x3C, 'shift_r': 0x3C,
    'capslock': 0x39, 'caps_lock': 0x39,
    'alt': 0x3A, 'lalt': 0x3A, 'alt_l': 0x3A, 'option': 0x3A, 'ralt': 0x3D, 'alt_r': 0x3D,
    'ctrl': 0x3B, 'control': 0x3B, 'lctrl': 0x3B, 'lcontrol': 0x3B, 'ctrl_l': 0x3B,
    'rctrl': 0x3E, 'rcontrol': 0x3E, 'ctrl_r': 0x3E,
    'f1': 0x7A, 'f2': 0x78, 'f3': 0x63, 'f4': 0x76, 'f5': 0x60, 'f6': 0x61,
    'f7': 0x62, 'f8': 0x64, 'f9': 0x65, 'f10': 0x6D, 'f11': 0x67, 'f12': 0x6F,
    'home': 0x73, 'pageup': 0x74, 'page_up': 0x74, 'delete': 0x75, 'end': 0x77,
    'pagedown': 0x79, 'page_down': 0x79,
    'left': 0x7B, 'right': 0x7C, 'down': 0x7D, 'up': 0x7E,
}


def get_cursor_pos():
    if Quartz is not None:
        try:
            ev = Quartz.CGEventCreate(None)
            loc = Quartz.CGEventGetLocation(ev)
            return int(round(loc.x)), int(round(loc.y))
        except Exception:
            pass
    return 0, 0


def set_cursor_pos(pos):
    if Quartz is not None:
        try:
            x, y = float(pos[0]), float(pos[1])
            Quartz.CGWarpMouseCursorPosition((x, y))
            Quartz.CGAssociateMouseAndMouseCursorPosition(True)
        except Exception:
            pass


class MacOSQuartzInteraction(BaseInteraction):
    """Native macOS Quartz CGEvent interaction method for keyboard and mouse control."""

    def __init__(self, capture: BaseCaptureMethod, hwnd_window):
        super().__init__(capture)
        self.hwnd_window = hwnd_window
        self.mouse_pos = (0, 0)
        self.check_clickable = True
        self._held_keys = set()
        self._held_buttons = {}

    @property
    def hwnd(self):
        if self.hwnd_window is None:
            return 0
        return self.hwnd_window.top_hwnd if self.hwnd_window.top_hwnd else self.hwnd_window.hwnd

    def clickable(self):
        return bool(self.hwnd_window and self.hwnd_window.is_foreground())

    def _require_foreground(self):
        if not self.clickable():
            self.on_destroy()
            raise TaskDisabledException('Game lost focus; input stopped')

    def _post_to_game(self, event, release=False):
        # Unreal's game input needs the HID event stream. Recheck focus at
        # dispatch instead of relying only on the public method's entry check.
        if self.clickable():
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        elif release:
            # Release held game inputs without sending new actions to another app.
            pid = get_window_pid(self.hwnd)
            if pid > 0:
                Quartz.CGEventPostToPid(pid, event)
        else:
            self._require_foreground()

    def on_destroy(self):
        for key in tuple(self._held_keys):
            self.send_key_up(key)
        for button in tuple(self._held_buttons):
            self.mouse_up(x=-1, y=-1, key=button)

    def should_capture(self):
        return True

    def activate(self, hwnd=None):
        if self.hwnd_window is not None and not self.hwnd_window.is_foreground():
            self.hwnd_window.bring_to_front()

    def deactivate(self, hwnd=None):
        pass

    def try_activate(self):
        self.activate()

    def on_run(self):
        if self.hwnd_window is not None:
            self.hwnd_window.bring_to_front()

    def _resolve_abs_coords(self, x, y):
        if x is not None and y is not None and x >= 0 and y >= 0:
            if self.capture is not None:
                abs_x, abs_y = self.capture.get_abs_cords(x, y)
            elif self.hwnd_window is not None:
                abs_x, abs_y = self.hwnd_window.get_abs_cords(x, y)
            else:
                abs_x, abs_y = int(x), int(y)
            self.mouse_pos = (abs_x, abs_y)
            return abs_x, abs_y
        if self.mouse_pos != (0, 0):
            return self.mouse_pos
        return get_cursor_pos()

    def _post_mouse_event(self, event_type, abs_x, abs_y, button=0, dx=0, dy=0):
        if Quartz is None:
            return
        up_types = {Quartz.kCGEventLeftMouseUp, Quartz.kCGEventRightMouseUp, Quartz.kCGEventOtherMouseUp}
        if event_type not in up_types:
            self._require_foreground()
        button_name = {Quartz.kCGMouseButtonLeft: 'left', Quartz.kCGMouseButtonRight: 'right', Quartz.kCGMouseButtonCenter: 'middle'}.get(button)
        try:
            ev = Quartz.CGEventCreateMouseEvent(None, event_type, (float(abs_x), float(abs_y)), button)
            if dx != 0 or dy != 0:
                Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventDeltaX, int(dx))
                Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventDeltaY, int(dy))
            self._post_to_game(ev, release=event_type in up_types)
            if event_type in up_types:
                self._held_buttons.pop(button_name, None)
            elif event_type in {Quartz.kCGEventLeftMouseDown, Quartz.kCGEventRightMouseDown, Quartz.kCGEventOtherMouseDown}:
                self._held_buttons[button_name] = (abs_x, abs_y)
        except TaskDisabledException:
            raise
        except Exception as e:
            logger.error(f"_post_mouse_event error: {e}")

    def send_key(self, key, down_time=0.01):
        super().send_key(key, down_time)
        self.send_key_down(key)
        time.sleep(down_time)
        self.send_key_up(key)

    def send_key_down(self, key, activate=True):
        # Activation is explicit at task startup; never steal focus back from
        # another app while a task is running, even with activate=True.
        self._require_foreground()
        key_str = str(key).lower()
        keycode = MAC_KEYCODE_MAP.get(key_str)
        if Quartz is None or keycode is None:
            raise ValueError(f'Unsupported macOS key: {key}')
        self._post_to_game(Quartz.CGEventCreateKeyboardEvent(None, keycode, True))
        self._held_keys.add(key_str)

    def send_key_up(self, key):
        key_str = str(key).lower()
        keycode = MAC_KEYCODE_MAP.get(key_str)
        if Quartz is not None and keycode is not None:
            self._post_to_game(Quartz.CGEventCreateKeyboardEvent(None, keycode, False), release=True)
        self._held_keys.discard(key_str)

    def input_text(self, text, activate=True):
        for char in str(text):
            self._require_foreground()
            if Quartz is None:
                raise RuntimeError('Quartz is unavailable')
            for down in (True, False):
                event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
                Quartz.CGEventKeyboardSetUnicodeString(event, len(char.encode('utf-16-le')) // 2, char)
                self._post_to_game(event, release=not down)

    def move(self, x, y, down_btn=0):
        self._require_foreground()
        abs_x, abs_y = self._resolve_abs_coords(x, y)
        if Quartz is not None:
            event_type = Quartz.kCGEventLeftMouseDragged if down_btn else Quartz.kCGEventMouseMoved
            self._post_mouse_event(event_type, abs_x, abs_y, Quartz.kCGMouseButtonLeft)
        return (abs_x, abs_y)

    def move_mouse_relative(self, dx, dy):
        self._require_foreground()
        cur_x, cur_y = get_cursor_pos()
        new_x, new_y = cur_x + int(dx), cur_y + int(dy)
        if Quartz is not None:
            self._post_mouse_event(
                Quartz.kCGEventMouseMoved,
                new_x,
                new_y,
                Quartz.kCGMouseButtonLeft,
                dx=int(dx),
                dy=int(dy),
            )
            self.mouse_pos = (new_x, new_y)

    def scroll(self, x, y, scroll_amount):
        self._require_foreground()
        if x > 0 and y > 0:
            self.move(x, y)
            time.sleep(0.01)
        if Quartz is not None:
            try:
                sign = 1 if scroll_amount > 0 else (-1 if scroll_amount < 0 else 0)
                for _ in range(abs(int(scroll_amount))):
                    self._require_foreground()
                    ev = Quartz.CGEventCreateScrollWheelEvent(
                        None, Quartz.kCGScrollEventUnitLine, 1, sign
                    )
                    self._post_to_game(ev)
                    time.sleep(0.002)
            except TaskDisabledException:
                raise
            except Exception as e:
                logger.error(f"scroll error: {e}")

    def swipe(self, x1, y1, x2, y2, duration=3, settle_time=0):
        self._require_foreground()
        abs_x1, abs_y1 = self._resolve_abs_coords(x1, y1)
        abs_x2, abs_y2 = self._resolve_abs_coords(x2, y2)

        self.move(x1, y1)
        time.sleep(0.05)
        self.mouse_down(x1, y1)

        steps = max(1, int(duration / 100) if duration > 10 else int(duration * 30))
        step_dx = (abs_x2 - abs_x1) / steps
        step_dy = (abs_y2 - abs_y1) / steps

        if Quartz is not None:
            for i in range(1, steps + 1):
                cx = abs_x1 + int(i * step_dx)
                cy = abs_y1 + int(i * step_dy)
                self._post_mouse_event(
                    Quartz.kCGEventLeftMouseDragged,
                    cx,
                    cy,
                    Quartz.kCGMouseButtonLeft,
                    dx=int(step_dx),
                    dy=int(step_dy),
                )
                time.sleep(0.01)

        if settle_time > 0:
            time.sleep(settle_time)
        self.mouse_up(key="left")

    def _button_types(self, key="left"):
        if Quartz is None:
            return 0, 0, 0
        if key == "right":
            return Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight
        if key == "middle":
            return Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, Quartz.kCGMouseButtonCenter
        return Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft

    def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01, move=True, key="left"):
        self._require_foreground()
        super().click(x, y, name=name)
        prev_pos = get_cursor_pos() if move_back else None
        abs_x, abs_y = self._resolve_abs_coords(x, y)

        if move and x != -1 and y != -1:
            self.move(x, y)
            time.sleep(max(0.005, down_time * 0.5))

        down_type, up_type, btn = self._button_types(key)
        self._post_mouse_event(down_type, abs_x, abs_y, btn)
        time.sleep(down_time)
        self._post_mouse_event(up_type, abs_x, abs_y, btn)

        if prev_pos is not None and self.clickable():
            set_cursor_pos(prev_pos)

    def right_click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01):
        self.click(x, y, move_back=move_back, name=name, down_time=down_time, key="right")

    def middle_click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01):
        self.click(x, y, move_back=move_back, name=name, down_time=down_time, key="middle")

    def mouse_down(self, x=-1, y=-1, name=None, key="left"):
        self._require_foreground()
        abs_x, abs_y = self._resolve_abs_coords(x, y)
        if x != -1 and y != -1:
            self.move(x, y)
        down_type, _, btn = self._button_types(key)
        self._post_mouse_event(down_type, abs_x, abs_y, btn)

    def mouse_up(self, x=-1, y=-1, key="left"):
        abs_x, abs_y = self._resolve_abs_coords(x, y)
        _, up_type, btn = self._button_types(key)
        self._post_mouse_event(up_type, abs_x, abs_y, btn)
