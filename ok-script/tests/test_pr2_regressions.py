from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from ok.device.interaction_methods.pynput import PynputInteraction


def test_pynput_releases_after_focus_loss_and_destruction():
    keyboard_controller, mouse_controller = MagicMock(), MagicMock()
    fake = SimpleNamespace(keyboard=SimpleNamespace(Controller=lambda: keyboard_controller, Key={}),
                           mouse=SimpleNamespace(Controller=lambda: mouse_controller,
                                                 Button=SimpleNamespace(left='left', right='right', middle='middle')))
    window = MagicMock()
    window.is_foreground.return_value = True
    with patch('ok.device.interaction_methods.pynput.sys.platform', 'win32'), patch.dict('sys.modules', {'pynput': fake}), patch('ok.device.interaction_methods.pynput.is_admin', return_value=True):
        backend = PynputInteraction(None, window)
        backend.send_key_down('w')
        backend.mouse_down()
        window.is_foreground.return_value = False
        backend.send_key_up('w')
        backend.mouse_up()
        keyboard_controller.release.assert_called_once_with('w')
        mouse_controller.release.assert_called_once_with('left')
        window.is_foreground.return_value = True
        backend.send_key_down('a')
        backend.mouse_down(key='right')
        window.is_foreground.return_value = False
        backend.on_destroy()
        keyboard_controller.release.assert_any_call('a')
        mouse_controller.release.assert_any_call('right')
        assert not backend._held_keys and not backend._held_buttons
        backend.on_destroy()
        assert keyboard_controller.release.call_count == 2
        assert mouse_controller.release.call_count == 2


def test_pynput_send_key_releases_when_sleep_is_interrupted():
    controller = MagicMock()
    fake = SimpleNamespace(keyboard=SimpleNamespace(Controller=lambda: controller, Key={}))
    with patch('ok.device.interaction_methods.pynput.sys.platform', 'win32'), patch.dict('sys.modules', {'pynput': fake}), patch('ok.device.interaction_methods.pynput.is_admin', return_value=True), patch('ok.device.interaction_methods.pynput.time.sleep', side_effect=RuntimeError('cancelled')):
        backend = PynputInteraction(None, MagicMock())
        with pytest.raises(RuntimeError):
            backend.send_key('w')
        controller.release.assert_called_once_with('w')


def test_combo_paint_accepts_pre_69_api():
    from ok.ui.qt.kit.inputs import ComboBox
    class ReachedLabel(Exception):
        pass
    def label():
        raise ReachedLabel()
    # A pre-6.9 instance has no labelDrawingMode method. Reach the normal
    # label path without constructing a native widget or invoking a painter.
    old_combo = SimpleNamespace(isEditable=lambda: False, _label_option=label)
    with pytest.raises(ReachedLabel):
        ComboBox.paintEvent(old_combo, None)
