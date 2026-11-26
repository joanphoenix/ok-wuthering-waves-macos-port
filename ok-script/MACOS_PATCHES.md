# macOS patches to ok-script

This folder is the official **ok-script 3.0.14** source release from PyPI (`ok_script-3.0.14.tar.gz`), with the changes below on top. Every file that differs from that release is listed here. Anything not listed is identical to upstream, so a future ok-script update can be applied as a plain diff between two releases.

To check that this list is complete, run:

```bash
python3 .github/scripts/sync_upstream.py --patches
```

The command downloads the release named in `.github/upstream.json`, compares it with this folder, and prints any changed file that this page doesn't mention. The macOS CI workflow runs it on every push.

When you change a file under `ok-script/` that isn't listed, add it to the right section with a short reason.

## New files

These files don't exist upstream.

### macOS platform layer

- `ok/device/capture_methods/macos_quartz.py`: captures the game window with CoreGraphics (Quartz).
- `ok/device/interaction_methods/macos_quartz.py`: sends keyboard and mouse input as Quartz events, and reports a missing Accessibility permission instead of posting silently.
- `ok/util/window_macos.py`: finds the game window and tracks its position, size and focus. Focus is read through the Process Manager, because `NSWorkspace` goes stale without a Cocoa run loop, and activation falls back to System Events.

### Web UI mode

Upstream ok-script 3.0 removed its web interface. This port keeps it for `./run_macos.sh --web` and `main_web.py`.

- `ok/ui/web/` (the whole package) and `ok/task/web.py`: the web server and its task bridge.
- `web_src/`, `package.json`, `package-lock.json`, `scripts/generate_web_i18n.py`, `scripts/run_python.mjs`: the front end and its build.
- `tests/test_web_app.py`, `tests/test_web_i18n.py`, `tests/test_web_server.py`, `tests/test_web_task_tabs.py`, `tests/test_web_ui_pages.py`, `tests/test_web_ui_tasks.py`: web UI tests.

### Tests and tooling

- `tests/conftest.py`: skips Windows-only test modules on other platforms.
- `tests/qt_helpers.py`: shared Qt test helpers.
- `tests/test_pr2_regressions.py`, `tests/test_runtime_reliability.py`: regression tests for port fixes.
- `pytest.ini`, `.gitignore`.
- `MACOS_PATCHES.md`: this page.

## Changed files

### Guards around Windows-only imports and calls

These modules import `win32api`, `win32gui`, `ctypes.windll`, `winreg` or similar at import time, or call Windows APIs unconditionally. The patch imports them only on Windows and skips or stubs the call elsewhere.

- `ok/core/screenshot.py`
- `ok/device/capture_methods/bitblt_utils.py`
- `ok/device/capture_methods/browser.py`
- `ok/device/capture_methods/desktop_duplication.py`
- `ok/device/capture_methods/hwnd_window.py`: also uses `window_macos` to find the game window.
- `ok/device/capture_methods/types.py`
- `ok/device/capture_methods/update.py`
- `ok/device/capture_methods/windows_graphics.py`
- `ok/device/interaction_methods/foreground_post_message.py`
- `ok/device/interaction_methods/genshin.py`
- `ok/device/interaction_methods/pydirect.py`
- `ok/notification/messenger_images.py`
- `ok/notification/windows_messenger.py`
- `ok/ui/overlay/win32_gdi.py`
- `ok/ui/qt/MainWindow.py`
- `ok/ui/qt/debug/OverlayWidget.py`: reads the cursor and modifier keys from Qt instead of `win32api`.
- `ok/ui/qt/debug/diagnosis_page.py`
- `ok/ui/qt/kit/window.py`
- `ok/ui/qt/shell/run_bar.py`: the Windows hotkey poll is off on macOS.
- `ok/ui/qt/tasks/RecordScript.py`
- `ok/ui/qt/tasks/schedule_index_sync.py`
- `ok/util/gpu_driver_settings.py`
- `ok/util/window.py`
- `ok/util/windows_schedule.py`: Task Scheduler is unavailable, so scheduling is a no-op.

### macOS input

- `ok/device/interaction_methods/post_message.py`: on macOS, the default "PostMessage" option is backed by Quartz input.
- `ok/device/interaction_methods/pynput.py`: uses native macOS keycodes for the keyboard, checks the input permission for the mouse, and reuses the pressing controller so moves during a hold drag.
- `ok/device/interaction_methods/keys.py`: defines the Windows key-code constants itself when pywin32 is missing.

### macOS runtime behaviour

- `ok/__init__.py`: skips Windows DPI setup, handles a missing Qt translation catalog, and starts the web UI when `gui.type` is `web`.
- `ok/util/process.py`: single-instance lock with `flock` instead of a Windows mutex.
- `ok/util/explorer.py`: opens folders in Finder.
- `ok/notification/system.py`: shows system notifications through macOS instead of the Windows tray API.
- `ok/task/TaskExecutor.py`: accepts 16:10 and similar MacBook aspect ratios for 16:9 games, and tolerates capture methods without `busy_wait`.
- `ok/device/DeviceManager.py`: hides the Windows 11 cloud-game device.
- `ok/ui/qt/about/UpdateCard.py`: an unsupported update check is logged as info, not as an error.

### macOS look and feel

- `ok/ui/qt/kit/theme.py`: system font and Menlo for monospace.
- `ok/ui/qt/util/app.py`: system font, and reuses an existing `QApplication`.
- `ok/ui/qt/kit/inputs.py`: works on PySide6 builds without `labelDrawingMode`.

### Web UI mode support in shared code

- `ok/cli.py`: adds the `ok web` command.
- `ok/core/ui_config.py`: accepts `gui.type: web` and its `launch_mode`.
- `ok/core/config_schema.py`, `ok/ui/qt/tasks/config_editors.py`: accept the type names that web-style configs use (`integer`, `number`, `boolean` and similar).
- `ok/core/template_store.py`, `ok/ui/qt/overlay/OverlayWindow.py`: docstrings only.

### Small fixes

- `ok/util/collection.py`: matching a saved option also works when the option label has a suffix.
- `ok/task/task.py`: `tr()` works before the app exists.
- `ok/test/__init__.py`: resets globals and the translator between game tests.
- `ok/ui/qt/settings/GlobalConfigTab.py`: properties the game's settings page uses.
- `ok/ui/qt/util/touch_scroll.py`: no error during interpreter shutdown.

### Packaging

- `pyproject.toml`: Windows-only dependencies are limited to Windows, PySide6 and pyobjc (including Vision, for the Korean Abyss prompt) are added for macOS, plus the `web` extra and web package data.
- `setup.py`: the `+macos.1` version.
- `README.md`: notes on the port.

### Tests changed for macOS or web mode

- `tests/test_cli.py`, `tests/test_headless_imports.py`, `tests/test_ui_config.py`: also cover web mode.
- `tests/test_executor_jobs.py`: fixes a timing race that failed on macOS CI.
- `tests/test_kit.py`: avoids a PySide6 crash on macOS when a temporary widget is collected.
- `tests/test_shell.py`: allows for the hidden Windows caption buttons.
- `tests/test_notifications.py`: Windows-only cases are skipped elsewhere.
- `tests/test_package_metadata.py`: expects the `web` extra.
- `tests/test_runtime_startup.py`, `tests/test_windows_schedule_target_parse.py`: extra macOS cases.
