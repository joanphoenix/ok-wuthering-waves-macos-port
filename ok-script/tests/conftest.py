"""Port-owned pytest configuration for the vendored ok-script tests.

The upstream suite targets Windows. Listing the Windows-only cases here keeps
the upstream test files byte-identical, so vendored merges stay conflict-free
while the suite can still run green on macOS.
"""

import importlib.util
import sys

import pytest

# Tests that drive Win32-only behaviour: Windows Graphics Capture selection,
# ``start``/``os.startfile`` launching, ``ctypes.windll`` window styling, and
# emulator paths resolved with Windows path semantics, and cloud-game browser
# geometry, which walks Chrome's Win32 child windows, and the GUI/console
# instance handoff, which matches python.exe/pythonw.exe pairs on Windows paths.
WINDOWS_ONLY = (
    "test_capture_update.py::TestCaptureUpdate::test_failed_wgc_start_is_cached_closed_and_falls_back",
    "test_capture_update.py::TestCaptureUpdate::test_busy_wgc_stays_selected_without_fallback_or_failure_cache",
    "test_device_manager.py::TestEmulatorWindowExe::test_resolves_mumu_12_instance_window",
    "test_device_manager.py::TestEmulatorWindowExe::test_resolves_mumu_15_instance_window",
    "test_process.py::TestProcessExecute::test_execute_can_use_os_startfile_when_configured",
    "test_process.py::TestProcessExecute::test_execute_uses_windows_start_command_by_default",
    "test_web_server.py::test_native_resize_handle_is_invisible_but_not_click_through",
    "test_web_server.py::test_rounded_window_region_tracks_native_window_size",
    "test_web_server.py::test_winforms_drag_move_uses_zero_size_with_nosize_flag",
    "test_process_mutex.py::TestProcessMutexMatching::test_virtual_environment_redirector_matches_its_command_line_interpreter",
    "test_process_mutex.py::TestGuiConsoleHandoff::test_gui_replaces_recorded_console_with_different_entry_script",
    "test_process_mutex.py::TestGuiConsoleHandoff::test_legacy_console_pid_marker_is_supported",
    "test_process_mutex.py::TestGuiConsoleHandoff::test_only_the_verified_console_owner_is_killed",
    "test_browser_geometry.py::TestBrowserGeometry::test_window_grows_to_fit_viewport_below_infobar_without_moving",
    "test_browser_geometry.py::TestBrowserGeometry::test_fitting_viewport_does_not_resize",
    "test_browser_geometry.py::TestBrowserGeometry::test_absolute_coordinates_include_native_client_border",
    "test_browser_geometry.py::TestBrowserGeometry::test_renderer_bounds_skip_hidden_windows_and_browser_controls",
    "test_browser_geometry.py::TestBrowserGeometry::test_crop_uses_renderer_origin_instead_of_assuming_symmetric_borders",
    "test_browser_geometry.py::TestBrowserGeometry::test_clipped_viewport_is_rejected_instead_of_shifting_crop_up",
)

# Emulator capture imports adbutils, which only the optional ``adb`` extra installs.
NEEDS_ADBUTILS = (
    "test_nemu_ipc_capture.py::TestNemuIpcCaptureMethod::test_first_capture_initializes_then_uses_screenshot",
)
# Modules that import adbutils while being collected.
NEEDS_ADBUTILS_MODULES = (
    "test_nemu_ipc_capture.py",
)

# These modules import pywin32 at module level, so they cannot be collected
# off Windows. They cover the Win32 PostMessage path, which the macOS port
# replaces with Quartz input.
WINDOWS_ONLY_MODULES = (
    "test_mouse_buttons.py",
    "test_post_message_activation.py",
    "test_windows_graphics_hdr.py",
)

collect_ignore = []
if sys.platform != "win32":
    collect_ignore.extend(WINDOWS_ONLY_MODULES)
if importlib.util.find_spec("adbutils") is None:
    collect_ignore.extend(NEEDS_ADBUTILS_MODULES)


def pytest_collection_modifyitems(items):
    windows = sys.platform == "win32"
    has_adbutils = importlib.util.find_spec("adbutils") is not None
    for item in items:
        if not windows and item.nodeid.endswith(WINDOWS_ONLY):
            item.add_marker(pytest.mark.skip(reason="exercises Windows-only behaviour"))
        elif not has_adbutils and item.nodeid.endswith(NEEDS_ADBUTILS):
            item.add_marker(pytest.mark.skip(reason="needs the optional adb extra (adbutils)"))
