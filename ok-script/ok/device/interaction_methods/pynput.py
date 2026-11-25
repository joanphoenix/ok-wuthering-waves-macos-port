import sys
import time

from ok.device.capture_methods.base import BaseCaptureMethod
from ok.device.interaction_methods.base import BaseInteraction
from ok.util.logger import Logger
from ok.util.process import is_admin

logger = Logger.get_logger(__name__)

class PynputInteraction(BaseInteraction):
    KEY_MAP = {
        'lshift': 'shift_l',
        'rshift': 'shift_r',
        'lctrl': 'ctrl_l',
        'rctrl': 'ctrl_r',
        'lalt': 'alt_l',
        'ralt': 'alt_r',
        'lcontrol': 'ctrl_l',
        'rcontrol': 'ctrl_r',
        'return': 'enter',
        'pageup': 'page_up',
        'pagedown': 'page_down',
        'capslock': 'caps_lock',
        'numlock': 'num_lock',
        'scrolllock': 'scroll_lock',
        'printscreen': 'print_screen',
        'windows': 'cmd',
        'win': 'cmd',
        'command': 'cmd',
        'meta': 'cmd'
    }
    def __init__(self, capture: BaseCaptureMethod, hwnd_window):
        super().__init__(capture)
        self.hwnd_window = hwnd_window
        self.check_clickable = True
        self._held_keys = {}
        self._held_buttons = {}
        self._native_keyboard = None
        if sys.platform == 'darwin':
            # Pynput Controller() queries Carbon's keyboard layout. Once Cocoa
            # text input is initialized, that query traps on the combat worker.
            # Native game keycodes avoid Carbon entirely, including in web mode.
            from ok.device.interaction_methods.macos_quartz import MacOSQuartzInteraction
            self._native_keyboard = MacOSQuartzInteraction(capture, hwnd_window)
        elif not is_admin():
            logger.error(f"You must be an admin to use PynputInteraction")

    def clickable(self):
        if self.check_clickable:
            return self.hwnd_window.is_foreground()
        else:
            return True

    def _parse_key(self, key):
        from pynput import keyboard
        if not isinstance(key, str):
            return key
        key_lower = key.lower()
        target_name = self.KEY_MAP.get(key_lower, key_lower)
        try:
            return keyboard.Key[target_name]
        except KeyError:
            return key

    def send_key(self, key, down_time=0.01):
        if not self.clickable():
            logger.error(f"can't click on {key}, because capture is not clickable")
            return

        self.send_key_down(key)
        try:
            time.sleep(down_time)
        finally:
            self.send_key_up(key)

    def send_key_down(self, key):
        if not self.clickable():
            logger.error(f"can't click on {key}, because capture is not clickable")
            return

        if self._native_keyboard is not None:
            self._native_keyboard.send_key_down(key)
            return
        from pynput import keyboard
        controller = keyboard.Controller()
        parsed_key = self._parse_key(str(key))
        controller.press(parsed_key)
        self._held_keys[parsed_key] = controller

    def send_key_up(self, key):
        if self._native_keyboard is not None:
            self._native_keyboard.send_key_up(key)
            return
        from pynput import keyboard
        parsed_key = self._parse_key(str(key))
        controller = self._held_keys.get(parsed_key)
        if controller is None:
            controller = keyboard.Controller()
        controller.release(parsed_key)
        self._held_keys.pop(parsed_key, None)

    def on_destroy(self):
        # Releases must remain possible after focus loss and task cancellation.
        if self._native_keyboard is not None:
            self._native_keyboard.on_destroy()
        for held in (self._held_keys, self._held_buttons):
            for value, controller in tuple(held.items()):
                try:
                    controller.release(value)
                    held.pop(value, None)
                except Exception as error:
                    logger.error(f'Could not release held input {value}: {error}')

    def scroll(self, x, y, scroll_amount):
        if not self.clickable():
            return
        if scroll_amount < 0:
            sign = -1
        elif scroll_amount > 0:
            sign = 1
        else:
            sign = 0
        logger.debug(f'pynput do_scroll {x}, {y}, {scroll_amount}')
        self.move(x, y)
        time.sleep(0.001)

        controller = self._new_mouse_controller()
        for i in range(abs(scroll_amount)):
            if not self.clickable():
                self.on_destroy()
                return
            controller.scroll(0, sign)
            time.sleep(0.001)
        time.sleep(0.02)

    def move(self, x, y):
        if not self.clickable():
            return

        abs_x, abs_y = self.capture.get_abs_cords(x, y)
        # pynput's macOS controller emits drag events only for a button it
        # pressed itself, so moves during a hold must reuse that controller.
        controller = next(iter(self._held_buttons.values()), None) or self._new_mouse_controller()
        controller.position = (abs_x, abs_y)

    def swipe(self, x1, y1, x2, y2, duration, settle_time=0):
        from pynput import mouse
        if not self.clickable():
            return
        x1, y1 = self.capture.get_abs_cords(x1, y1)
        x2, y2 = self.capture.get_abs_cords(x2, y2)
        controller = self._new_mouse_controller()
        controller.position = (x1, y1)
        time.sleep(0.1)
        if not self.clickable():
            return
        controller.press(mouse.Button.left)
        self._held_buttons[mouse.Button.left] = controller
        try:
            steps = max(1, int(duration / 100))
            for i in range(1, steps + 1):
                if not self.clickable():
                    return
                controller.position = (x1 + int(i * (x2 - x1) / steps),
                                       y1 + int(i * (y2 - y1) / steps))
                time.sleep(0.01)
        finally:
            self.mouse_up()
        if settle_time:
            time.sleep(settle_time)

    def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01, move=False, key="left"):
        from pynput import mouse
        super().click(x, y, name=name)
        if not self.clickable():
            logger.info(f"window in background, not clickable")
            return

        controller = self._new_mouse_controller()
        current_pos = None
        if move_back:
            current_pos = controller.position

        if x != -1 and y != -1:
            abs_x, abs_y = self.capture.get_abs_cords(x, y)
            logger.info(f"left_click {abs_x, abs_y}")
            controller.position = (abs_x, abs_y)
            time.sleep(0.02)

        button = self.get_mouse_button(key)
        if not self.clickable():
            return
        controller.press(button)
        self._held_buttons[button] = controller
        try:
            time.sleep(down_time)
        finally:
            self.mouse_up(key)
            if current_pos is not None and self.clickable():
                controller.position = current_pos

    def mouse_down(self, x=-1, y=-1, name=None, key="left"):
        from pynput import mouse
        if not self.clickable():
            logger.info(f"window in background, not clickable")
            return

        controller = self._new_mouse_controller()
        if x != -1 and y != -1:
            abs_x, abs_y = self.capture.get_abs_cords(x, y)
            logger.info(f"mouse_down {abs_x, abs_y}")
            controller.position = (abs_x, abs_y)
            time.sleep(0.02)

        if not self.clickable():
            return
        button = self.get_mouse_button(key)
        controller.press(button)
        self._held_buttons[button] = controller

    def get_mouse_button(self, key):
        from pynput import mouse
        if key == "right":
            return mouse.Button.right
        if key == "middle":
            return mouse.Button.middle
        return mouse.Button.left

    def _new_mouse_controller(self):
        if self._native_keyboard is not None:
            self._native_keyboard._require_input_permission()
        from pynput import mouse
        return mouse.Controller()

    def mouse_up(self, key="left"):
        from pynput import mouse
        button = self.get_mouse_button(key)
        controller = self._held_buttons.get(button)
        if controller is None:
            controller = mouse.Controller()
        controller.release(button)
        self._held_buttons.pop(button, None)

    def should_capture(self):
        return self.clickable()

    def on_run(self):
        self.hwnd_window.bring_to_front()
