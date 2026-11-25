from types import SimpleNamespace
import sys
from unittest.mock import MagicMock, patch

try:
    import pytest
except ImportError:
    # Windows CI loads this module through unittest and does not install pytest.
    pytest = None

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
    from PySide6.QtWidgets import QApplication, QSpinBox
    from ok.ui.qt.kit.inputs import NumberBox
    from ok.ui.qt.util.macos_compat import fix_spinbox_layout
    global _test_qt_app
    _test_qt_app = QApplication.instance() or QApplication([])
    # The live tasks page uses the kit number box, which does not need Fluent widgets.
    box = NumberBox(1, minimum=1, maximum=21)
    assert box.spin_box.lineEdit().text() == '1'
    box.plus_button.click()
    assert box.value() == 2
    widget = QSpinBox()
    with patch('ok.ui.qt.util.macos_compat.sys.platform', 'win32'):
        original = widget.styleSheet()
        fix_spinbox_layout(widget)
        assert widget.styleSheet() == original
    widget.deleteLater()
    box.deleteLater()


def test_activation_uses_native_api_without_system_events():
    appkit = MagicMock()
    with patch.object(windows, 'get_window_pid', return_value=42), patch.object(windows, '_appkit', return_value=appkit), \
            patch.object(windows, 'is_foreground_window', return_value=True), patch.object(windows.subprocess, 'run') as scripts:
        assert windows.bring_window_to_front(7)
        appkit.NSRunningApplication.runningApplicationWithProcessIdentifier_.assert_called_once_with(42)
        scripts.assert_not_called()


def test_activation_falls_back_to_system_events_when_native_activation_is_ignored():
    # macOS 14+ ignores NSApplicationActivateIgnoringOtherApps from a background process.
    appkit = MagicMock()
    with patch.object(windows, 'get_window_pid', return_value=42), patch.object(windows, '_appkit', return_value=appkit), \
            patch.object(windows, '_wait_foreground', side_effect=[False, True]), \
            patch.object(windows.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stderr='')) as scripts:
        assert windows.bring_window_to_front(7)
        command = scripts.call_args.args[0]
        assert command[0] == 'osascript'
        assert 'set frontmost of (first process whose unix id is 42) to true' in command[2]


def test_activation_reports_failure_when_system_events_is_refused_or_game_stays_behind():
    appkit = MagicMock()
    with patch.object(windows, 'get_window_pid', return_value=42), patch.object(windows, '_appkit', return_value=appkit), \
            patch.object(windows, '_wait_foreground', return_value=False):
        with patch.object(windows.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr='not allowed')):
            assert not windows.bring_window_to_front(7)
        with patch.object(windows.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stderr='')):
            assert not windows.bring_window_to_front(7)


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
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=MagicMock(side_effect=[True, False, True]))
    with patch.object(inputs, 'Quartz', quartz):
        interaction = inputs.MacOSQuartzInteraction(None, window)
        with pytest.raises(TaskDisabledException):
            interaction.send_key_down('r')
        assert not interaction._held_keys
        assert window.is_foreground.call_count == 2
        quartz.CGEventPost.assert_not_called()
        quartz.CGEventPostToPid.assert_not_called()


def test_swipe_releases_where_the_drag_ended():
    quartz = MagicMock()
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=lambda: True,
                             get_abs_cords=lambda x, y: (x, y))
    with patch.object(inputs, 'Quartz', quartz), patch.object(inputs.time, 'sleep'):
        interaction = inputs.MacOSQuartzInteraction(None, window)
        interaction.swipe(100, 100, 400, 300, 700)
    mouse_events = [call.args[1:3] for call in quartz.CGEventCreateMouseEvent.call_args_list]
    assert mouse_events[-2] == (quartz.kCGEventLeftMouseDragged, (400.0, 300.0))
    # Releasing at the start point would drag the content back again.
    assert mouse_events[-1] == (quartz.kCGEventLeftMouseUp, (400.0, 300.0))
    assert not interaction._held_buttons


def test_swipe_interrupted_by_focus_loss_releases_once():
    quartz = MagicMock()
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=MagicMock(return_value=True),
                             get_abs_cords=lambda x, y: (x, y))

    def lose_focus_after_press(_tap, _event):
        if quartz.CGEventPost.call_count == 3:  # move, move, button down
            window.is_foreground.return_value = False

    quartz.CGEventPost.side_effect = lose_focus_after_press
    with patch.object(inputs, 'Quartz', quartz), patch.object(inputs.time, 'sleep'), \
            patch.object(inputs, 'get_window_pid', return_value=42):
        interaction = inputs.MacOSQuartzInteraction(None, window)
        with pytest.raises(TaskDisabledException):
            interaction.swipe(100, 100, 400, 300, 700)
    assert not interaction._held_buttons
    assert quartz.CGEventPostToPid.call_count == 1


def test_web_launch_mode_still_resolves():
    # main_web.py and `run_macos.sh --web` need the web type. Upstream ok-script
    # dropped it, so a vendored merge can silently break the web launch again.
    from ok.core.ui_config import resolve_ui_config
    resolved = resolve_ui_config({'gui': {'type': 'web', 'launch_mode': 'pywebview'}})
    assert (resolved['type'], resolved['launch_mode']) == ('web', 'pywebview')


def test_denied_input_permission_reports_instead_of_silently_posting():
    quartz = MagicMock()
    quartz.CGPreflightPostEventAccess.return_value = False
    window = SimpleNamespace(hwnd=7, top_hwnd=0, is_foreground=lambda: True,
                             get_abs_cords=lambda x, y: (x, y))
    with patch.object(inputs, 'Quartz', quartz), \
         patch('ok.core.notifications.alert_error') as alert:
        interaction = inputs.MacOSQuartzInteraction(None, window)
        for action in [lambda: interaction.send_key_down('e'),
                       lambda: interaction.mouse_down(10, 10)]:
            with pytest.raises(PermissionError, match='Accessibility'):
                action()
        quartz.CGEventPost.assert_not_called()
        alert.assert_called_once()
        assert 'Claude Code' in alert.call_args.args[0]

        # Granting permission should immediately allow a retry in this process.
        quartz.CGPreflightPostEventAccess.return_value = True
        interaction.send_key_down('e')
        quartz.CGEventPost.assert_called_once()
        # Releases remain possible if permission changes while input is held.
        quartz.CGPreflightPostEventAccess.return_value = False
        interaction.send_key_up('e')
        assert not interaction._held_keys
        assert quartz.CGEventPost.call_count == 2


def test_coordinate_free_attack_uses_cursor_after_move_back():
    quartz = MagicMock()
    window = SimpleNamespace(is_foreground=lambda: True,
                             get_abs_cords=lambda x, y: (x, y))
    with patch.object(inputs, 'Quartz', quartz), patch.object(inputs.time, 'sleep'), \
            patch.object(inputs, 'get_cursor_pos', return_value=(80, 90)), \
            patch.object(inputs, 'set_cursor_pos') as restore:
        interaction = inputs.MacOSQuartzInteraction(None, window)
        interaction.click(400, 500, move_back=True)
        restore.assert_called_once_with((80, 90))
        quartz.CGEventCreateMouseEvent.reset_mock()
        interaction.click()
        assert [call.args[2] for call in quartz.CGEventCreateMouseEvent.call_args_list] == [
            (80.0, 90.0), (80.0, 90.0)
        ]


def test_macos_hides_cloud_device_and_migrates_saved_selection():
    from ok.device.DeviceManager import DeviceManager

    manager = DeviceManager.__new__(DeviceManager)
    manager.config = {'preferred': 'browser', 'capture': 'browser'}
    manager.windows_capture_config = {'capture_method': ['WGC', 'BitBlt_RenderFull']}
    native = {'imei': 'pc', 'device': 'windows', 'connected': True}
    manager.device_dict = {
        'browser': {'imei': 'browser', 'device': 'browser'},
        'adb': {'imei': 'adb', 'device': 'adb', 'connected': True},
        'pc': native,
    }
    manager.start = MagicMock()
    with patch('ok.device.DeviceManager.sys.platform', 'darwin'), \
            patch('ok.core.notifications.alert_info') as alert:
        assert manager.get_preferred_device() is None
        manager.update_browser_device()
        assert 'browser' not in manager.device_dict
        assert manager.get_preferred_device() is native
        assert manager.get_preferred_capture() == 'WGC'
        alert.assert_called_once()


def test_macos_foreground_requires_the_active_application():
    quartz = SimpleNamespace(kCGWindowOwnerPID='pid', kCGWindowIsOnscreen='onscreen')
    window = {'pid': 42, 'onscreen': True}
    with patch.object(windows, '_quartz', return_value=quartz), \
            patch.object(windows, '_frontmost_pid') as frontmost, \
            patch.object(windows, '_get_window_dict', return_value=window):
        frontmost.return_value = 99  # another app, even without a window
        assert not windows.is_foreground_window(7)
        frontmost.return_value = 42
        assert windows.is_foreground_window(7)
        window['onscreen'] = False
        assert not windows.is_foreground_window(7)


def test_frontmost_app_does_not_depend_on_a_cocoa_run_loop():
    # NSWorkspace stays stale without a main run loop (web server and headless
    # runs), which would keep sending input after the user switched apps.
    appkit = MagicMock()
    appkit.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier.return_value = 42
    with patch.object(windows, '_appkit', return_value=appkit):
        with patch.object(windows, '_process_manager_pid', return_value=lambda: 99):
            assert windows._frontmost_pid() == 99
        with patch.object(windows, '_process_manager_pid', return_value=lambda: None):
            assert windows._frontmost_pid() is None  # a failed query is not foreground
        with patch.object(windows, '_process_manager_pid', return_value=None):
            assert windows._frontmost_pid() == 42  # API removed: AppKit is all that is left
    if sys.platform == 'darwin':
        assert windows._process_manager_pid() is not None


def test_unsupported_cloud_requests_preserve_native_device_settings():
    from ok.device.DeviceManager import DeviceManager

    manager = DeviceManager.__new__(DeviceManager)
    manager.config = {'preferred': 'pc', 'pc_full_path': '/Applications/Wuthering Waves.app'}
    manager.device_dict = {'pc': {'imei': 'pc', 'device': 'windows'}}
    manager.clear_devices = MagicMock()
    with patch('ok.device.DeviceManager.sys.platform', 'darwin'):
        for request_capture in (manager.update_capture, manager.ensure_capture):
            with pytest.raises(ValueError, match='requires Windows'):
                request_capture({'browser': {}})
    manager.clear_devices.assert_not_called()
    assert manager.get_preferred_device() is manager.device_dict['pc']
