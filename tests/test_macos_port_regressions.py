from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ok.device.interaction_methods import macos_quartz as inputs
from ok.task.exceptions import TaskDisabledException
from ok.util import window_macos as windows


def test_input_stops_on_focus_loss_and_releases_only_to_game():
    quartz = MagicMock()
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=MagicMock(return_value=True))
    with patch.object(inputs, 'Quartz', quartz), patch.object(inputs, 'get_window_pid', return_value=42):
        interaction = inputs.MacOSQuartzInteraction(None, window)
        interaction.send_key_down('w')
        window.is_foreground.return_value = False
        with pytest.raises(TaskDisabledException):
            interaction.send_key_down('f')
        assert not interaction._held_keys
        assert quartz.CGEventPostToPid.call_count == 1
        assert quartz.CGEventPost.call_count == 1
        quartz.CGEventCreateKeyboardEvent.assert_any_call(None, inputs.MAC_KEYCODE_MAP['w'], False)
        for action in [lambda: interaction.click(10, 10), lambda: interaction.scroll(0, 0, 1),
                       lambda: interaction.input_text('hello'), lambda: interaction.move(10, 10)]:
            with pytest.raises(TaskDisabledException):
                action()
        assert quartz.CGEventPostToPid.call_count == 1


def test_foreground_input_uses_game_compatible_hid_stream():
    quartz = MagicMock()
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=lambda: True)
    with patch.object(inputs, 'Quartz', quartz), patch.object(inputs, 'get_window_pid', return_value=42):
        interaction = inputs.MacOSQuartzInteraction(None, window)
        interaction.send_key('f', down_time=0)
        interaction.input_text('x')
        assert quartz.CGEventPost.call_count == 4
        quartz.CGEventPostToPid.assert_not_called()


def test_scale_refreshes_on_display_change_without_window_resize():
    quartz = MagicMock()
    quartz.CGImageGetWidth.side_effect = [1600, 800, 800]
    quartz.CGImageGetHeight.side_effect = [900, 450, 450]
    windows._window_metrics_cache.clear()
    with patch.object(windows, '_quartz', return_value=quartz), patch.object(windows, '_detect_title_bar_pixels_from_cgimage', return_value=0):
        assert windows._get_window_scale_and_title_bar(0, 0, 800, 450, 7)[0] == 2
        assert windows._get_window_scale_and_title_bar(2000, 0, 800, 450, 7)[0] == 1
        # Also refresh backing resolution with an unchanged origin (display settings).
        assert windows._get_window_scale_and_title_bar(0, 0, 800, 450, 7)[0] == 1
    windows._window_metrics_cache.clear()


def test_focus_loss_releases_held_mouse_button():
    quartz = MagicMock()
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=MagicMock(return_value=True),
                             get_abs_cords=lambda x, y: (x, y))
    with patch.object(inputs, 'Quartz', quartz), patch.object(inputs, 'get_window_pid', return_value=42):
        interaction = inputs.MacOSQuartzInteraction(None, window)
        interaction.mouse_down(10, 10)
        window.is_foreground.return_value = False
        with pytest.raises(TaskDisabledException):
            interaction.move(20, 20)
        assert not interaction._held_buttons
        quartz.CGEventCreateMouseEvent.assert_any_call(None, quartz.kCGEventLeftMouseUp, (10.0, 10.0), quartz.kCGMouseButtonLeft)
        assert quartz.CGEventPost.call_count == 2
        assert quartz.CGEventPostToPid.call_count == 1


def test_spinbox_installer_is_idempotent_and_windows_is_untouched():
    import sys
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import SpinBox
    from qfluentwidgets.components.widgets.spin_box import SpinBoxBase
    from qfluentwidgets.common import style_sheet
    from ok.ui.qt.util.macos_compat import install_macos_compatibility, fix_spinbox_layout
    global _test_qt_app
    _test_qt_app = QApplication.instance() or QApplication([])
    if sys.platform == 'darwin':
        install_macos_compatibility()
        first = SpinBoxBase.__init__
        sheet = style_sheet.getStyleSheetFromFile
        install_macos_compatibility()
        assert SpinBoxBase.__init__ is first
        assert style_sheet.getStyleSheetFromFile is sheet
    widget = SpinBox()
    with patch('ok.ui.qt.util.macos_compat.sys.platform', 'win32'):
        original = widget.styleSheet()
        fix_spinbox_layout(widget)
        assert widget.styleSheet() == original
    widget.deleteLater()


def test_activation_uses_native_api_without_system_events():
    appkit = MagicMock()
    with patch.object(windows, 'get_window_pid', return_value=42), patch.object(windows, '_appkit', return_value=appkit), patch.object(windows.subprocess, 'run') as scripts:
        assert windows.bring_window_to_front(7)
        appkit.NSRunningApplication.runningApplicationWithProcessIdentifier_.assert_called_once_with(42)
        scripts.assert_not_called()


def test_capture_rejects_transient_geometry_and_ignores_old_discovery_crop():
    import numpy as np
    from ok.device.capture_methods import macos_quartz as capture
    quartz = MagicMock()
    quartz.CGImageGetWidth.return_value = 1280
    quartz.CGImageGetHeight.return_value = 720
    quartz.CGImageGetBytesPerRow.return_value = 1280 * 4
    quartz.CGDataProviderCopyData.return_value = np.zeros((720, 1280, 4), dtype=np.uint8).tobytes()
    window = SimpleNamespace(hwnd=7, window_width=280, window_height=120, client_width=280, client_height=120,
                             real_width=280, real_height=120, width=280, height=120, real_x_offset=0, real_y_offset=0)
    with patch.object(capture, 'Quartz', quartz):
        method = capture.MacOSQuartzCaptureMethod(window)
        assert method.do_get_frame() is None
        window.window_width = window.client_width = 1280
        window.window_height = window.client_height = 720
        assert method.do_get_frame().shape == (720, 1280, 3)


def test_focus_is_rechecked_at_event_dispatch():
    quartz = MagicMock()
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=MagicMock(side_effect=[True, False, False]))
    with patch.object(inputs, 'Quartz', quartz):
        interaction = inputs.MacOSQuartzInteraction(None, window)
        with pytest.raises(TaskDisabledException):
            interaction.send_key_down('r')
        quartz.CGEventPost.assert_not_called()
        quartz.CGEventPostToPid.assert_not_called()
