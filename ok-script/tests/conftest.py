"""Port-owned pytest configuration for the vendored ok-script tests.

The upstream suite targets Windows. Listing the Windows-only cases here keeps
the upstream test files byte-identical, so vendored merges stay conflict-free
while the suite can still run green on macOS.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# Tests that drive Win32-only behaviour: Windows Graphics Capture selection,
# ``start``/``os.startfile`` launching, ``ctypes.windll`` window styling, and
# emulator paths resolved with Windows path semantics.
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
)

# Emulator capture imports adbutils, which only the optional ``adb`` extra installs.
NEEDS_ADBUTILS = (
    "test_nemu_ipc_capture.py::TestNemuIpcCaptureMethod::test_first_capture_initializes_then_uses_screenshot",
)

# The MCP end-to-end cases read upstream's consumer skills from ok-script/.agents,
# which this port does not vendor. tests/test_macos_port_regressions.py covers the
# server's authentication and origin checks instead.
NEEDS_CONSUMER_SKILLS = (
    "test_mcp_server.py::test_http_connection_and_tools_end_to_end[auto]",
    "test_mcp_server.py::test_http_connection_and_tools_end_to_end[legacy]",
)

# These modules import pywin32 at module level, so they cannot even be collected
# elsewhere.
WINDOWS_ONLY_MODULES = (
    "test_post_message_activation.py",
)

collect_ignore = []
if sys.platform != "win32":
    collect_ignore.extend(WINDOWS_ONLY_MODULES)


def pytest_collection_modifyitems(items):
    windows = sys.platform == "win32"
    has_adbutils = importlib.util.find_spec("adbutils") is not None
    has_consumer_skills = (Path(__file__).resolve().parents[1] / ".agents/skills/develop").is_dir()
    for item in items:
        if not windows and item.nodeid.endswith(WINDOWS_ONLY):
            item.add_marker(pytest.mark.skip(reason="exercises Windows-only behaviour"))
        elif not has_adbutils and item.nodeid.endswith(NEEDS_ADBUTILS):
            item.add_marker(pytest.mark.skip(reason="needs the optional adb extra (adbutils)"))
        elif not has_consumer_skills and item.nodeid.endswith(NEEDS_CONSUMER_SKILLS):
            item.add_marker(pytest.mark.skip(reason="upstream consumer skills are not vendored"))
