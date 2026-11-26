# ok-wuthering-waves-macos-port

A macOS Apple Silicon port of [ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves), an image-recognition automation tool for *Wuthering Waves*, built with [ok-script](https://github.com/ok-oldking/ok-script).

This fork tracks upstream [v3.8.16](https://github.com/ok-oldking/ok-wuthering-waves/releases/tag/v3.8.16) and includes a vendored **ok-script 3.0.15b1**: the official release plus the macOS changes listed in [ok-script/MACOS_PATCHES.md](ok-script/MACOS_PATCHES.md). macOS screen capture, input, game discovery, and UI adaptations are maintained in this repository.

## Features

- **Combat and exploration:** automatic combat, item pickup, dialogue skipping, login, and fast travel tasks.
- **Daily activities and farming:** daily tasks, Echo farming, Nightmare Nests, Tacet Fields, Forgery Challenges, and Simulation Challenges.
- **Echo management:** merge, enhance, and change Echoes.
- **Additional tasks:** multi-account configuration and daily tasks, Garden, Rahai Blocks, and the 3.8 GalGame event.
- **Character-specific combat logic:** includes Suoming (锁瞑) heavy attacks and burst sequences, and Douling (卜灵) Trigram detection.

Cultivation Resource Farm, Rahai Blocks, and the GalGame event are listed only when the app language is Simplified Chinese; Cultivation Resource Farm and Rahai Blocks also require a 16:9 game window.

These are tasks registered by the current [configuration](config.py). Availability in the UI does not establish that every task or character rotation has been verified on every macOS version.

## Requirements and compatibility

| Component | Requirement or current scope |
| --- | --- |
| Hardware | Apple Silicon Mac with a native `arm64` Python interpreter |
| macOS | The oldest working release has not been established by a version-by-version test matrix; dependency requirements also apply |
| Python | **3.12.x**, installed before running the launcher |
| Git | Required to clone and update the repository |
| Game | Native macOS *Wuthering Waves* client, identified as `Client-Mac-Shipping` |
| Game display | **16:9**, at least **1280 × 720**; configured resize targets are 1280 × 720, 1600 × 900, 1920 × 1080, and 2560 × 1440 |
| Permissions | Screen Recording and Accessibility for the app hosting the Python process |
| Network | Needed to clone the repository and download dependencies on initial setup or dependency refresh |

Apple Silicon is the intended platform; Intel Macs and Rosetta Python environments are outside this guide's supported setup. The [macOS CI workflow](.github/workflows/macos.yml) runs launcher and runtime regression tests on `macos-latest` with Python 3.12. It does not establish a minimum macOS version or validate live gameplay across hardware generations.

Game discovery checks both `/Applications` and `~/Applications` for either `Wuthering Waves.app` or `WutheringWaves.app`. See [config.py](config.py) for the discovery logic.

## Quick start

### 1. Install and check prerequisites

If you already have [Homebrew](https://docs.brew.sh/Installation), install Git and [Python 3.12](https://formulae.brew.sh/formula/python@3.12):

```bash
brew install git python@3.12
```

If you use another Python distribution, ensure its `python3.12` command is available in your terminal. A different Python minor version does not satisfy the launcher check.

Verify the tools before continuing:

```bash
git --version
python3.12 -c 'import platform, sys; print(sys.version); print(platform.machine()); assert sys.version_info[:2] == (3, 12); assert platform.machine() == "arm64"'
```

The Python check must report Python 3.12 and `arm64`. If it reports `x86_64`, open a native terminal session and use an Apple Silicon Python installation.

### 2. Clone the repository

```bash
git clone https://github.com/joanphoenix/ok-wuthering-waves-macos-port.git
cd ok-wuthering-waves-macos-port
```

The public HTTPS URL works without configuring GitHub SSH keys.

### 3. Grant macOS permissions

Open **System Settings → Privacy & Security** and enable the following for the host you use to launch the tool, such as Terminal, iTerm, or your IDE:

| Permission | Purpose |
| --- | --- |
| Screen Recording, or Screen & System Audio Recording | Read the game window |
| Accessibility | Send keyboard and mouse input |

Follow any macOS prompt to quit and reopen the host after changing permissions, then relaunch the tool. If macOS lists the Python process separately, grant permission to that entry as well.

### 4. Launch the application

```bash
chmod +x run_macos.sh
./run_macos.sh
```

The launcher creates a local `.venv`, installs dependencies, and starts the Qt application. **It does not install Python itself.** The first launch can take longer while packages download.

An interrupted dependency installation is retried on the next launch. Changes to the launcher or project dependency metadata invalidate the installation stamp and trigger a refresh. Use this launcher for the macOS dependency setup.

### 5. Prepare the game and start a task

1. Open the native game client and enter the game.
2. Set a 16:9 game resolution of at least 1280 × 720.
3. Match the tool's **Game Hotkey** settings to your in-game bindings. For example, the configured defaults use `Q` for Echo, `E` for Resonance Skill, and `R` for Liberation.
4. Equip a main Echo on every team member before using Auto Combat, and disable in-game Auto Sprint.
5. Review the selected task's settings, start it, and return focus to the game.

Keep the game visible and in the foreground while automation runs. Switching to another app stops input and releases held keys and buttons to the game process. Return to the game before restarting the interrupted task.

## Launch modes

Run these commands from the repository folder:

| Mode | Command | Behavior |
| --- | --- | --- |
| Qt application | `./run_macos.sh` | Default desktop interface |
| Web UI in an embedded window | `./run_macos.sh --web` | Starts a local web server and displays the interface through pywebview |
| Qt debug mode | `./run_macos.sh --debug` | Starts the debug entry point |

The first `--web` launch installs the web dependencies. Switching modes can refresh the dependency stamp.

The web server binds to `127.0.0.1` on an automatically selected port. The web runtime also supports browser and server launch modes, but `--web` selects the embedded window. There is no dedicated browser-mode flag in `run_macos.sh`; see [main_web.py](main_web.py) and the [web server implementation](ok-script/ok/ui/web/server.py) for development configuration.

Opening the tool twice leaves the existing instance running. Close it before starting another instance.

## macOS implementation

- **Capture:** on macOS 14 and later, the game window is streamed with ScreenCaptureKit. On older macOS, or if ScreenCaptureKit fails, the tool uses CoreGraphics (Quartz) window capture, which Apple has deprecated. To force Quartz capture, launch with `OK_MAC_CAPTURE=quartz ./run_macos.sh`.
- **Input:** the default `PostMessage` option maps to Quartz events on macOS. The alternative `Pynput` option uses native game keycodes for the keyboard and Pynput for the mouse.
- **Inference:** YOLOv8 attempts to use the ONNX Runtime CoreML execution provider when available, with CPU fallback. PP-OCRv6 OCR currently runs on CPU.
- **Interface:** macOS typography, traffic-light window controls, global menu integration, system accent colors, light/dark themes, and Dock reactivation.

Desktop shortcuts include **Cmd + ,** for Preferences, **Cmd + Q** to quit, **Cmd + W** to close the window, and **Cmd + 1–5** for tab navigation. Shortcut availability depends on the active interface.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `git` or `python3.12` is missing | Complete the prerequisite installation, reopen the terminal, and repeat the version checks. |
| `Python 3.12 is required` | Ensure `python3.12` is on your PATH. The launcher falls back to `python3` only if `python3.12` is unavailable, and still requires version 3.12. |
| `Recreate .venv with Python 3.12` | Close the tool, rename `.venv` to an unused backup name, and run the launcher again with Python 3.12 available. Keep `configs/` in place. |
| Dependency download or installation fails | Read the first error in the terminal, check your network connection and Python architecture, then rerun the same launch command. Failed installs do not receive a completion stamp. |
| Game is not detected | Start the native game client and check its app name and location against the discovery paths above. |
| Capture is blank or unavailable | Check Screen Recording permission for the actual launch host, follow restart prompts, and keep the game visible. |
| The game is detected but receives no input | Check Accessibility permission, bring the game to the foreground, and verify Game Hotkey settings. |
| Automation pauses after moving or minimizing the game | Restore it to a visible display, bring it to the foreground, and restart the interrupted task. |
| A second launch appears to do nothing | Check for an existing instance and close it before relaunching. |
| Combat repeatedly locks onto enemies without attacking | Check that every character has a main Echo equipped, confirm keybindings, and check game focus. |

### Logs and bug reports

Logs are configured relative to the repository folder:

- `logs/ok-ww.log` — application log.
- `logs/ok-ww_error.log` — application errors.
- `logs/launcher.log` and `logs/launcher_error.log` — launcher logs when that launcher path is used.

Early shell or dependency-installation errors may appear only in the terminal. Include that output when reporting startup failures.

[Open an issue in this fork](https://github.com/joanphoenix/ok-wuthering-waves-macos-port/issues) with your macOS version, Mac chip, Python version and architecture, repository commit, launch mode, game resolution, steps to reproduce, and relevant logs. Remove personal information from logs and screenshots before sharing them.

## Updating and development

The app can update itself: open **About**, click **Check for updates**, pick `main` and click **Update**. The app closes, updates the checkout, and starts again. The macOS launcher checks dependencies during that restart, including changes to the vendored package and the web extras. This needs a checkout without changes to tracked files.

To update by hand instead: before updating, stop automation and close the tool. Review local changes with `git status`, then update a clean checkout:

```bash
git pull --ff-only
./run_macos.sh
```

If Git reports local changes or diverged history, resolve those before updating. Keep `configs/` when rebuilding the Python environment.

- [Upstream changelog](CHANGELOG.md)
- [Contributor guide](docs/development/contributing.md)
- [Multi-account configuration](docs/multi-account-config.md)
- [Vendored ok-script](ok-script)

Some inherited documentation describes Windows behavior, dependencies, and background automation. Use this README and `run_macos.sh` for macOS setup and foreground-input requirements.

### Syncing with upstream

The upstream release and ok-script version this fork tracks are recorded in [`.github/upstream.json`](.github/upstream.json). Every day, the [Upstream sync workflow](.github/workflows/upstream_sync.yml) checks for newer upstream releases. When it finds one, it opens a pull request named `Sync with upstream vX.Y.Z`, as a draft if any files need manual merging. You can also run the workflow from the Actions tab and choose a tag.

To sync by hand from a clean checkout, run:

```bash
python3 .github/scripts/sync_upstream.py --check   # show the releases this fork is missing
python3 .github/scripts/sync_upstream.py           # apply them, writing upstream-sync-report.md
```

The fork shares no git history with upstream, so the script applies the diff between two upstream release tags with a 3-way merge. When the release moves the ok-script pin, it also applies the diff between the two ok-script PyPI source releases to `ok-script/`. Files that need attention are listed in the report. When resolving conflicts, keep the macOS code paths. If you change a file under `ok-script/`, list it in [MACOS_PATCHES.md](ok-script/MACOS_PATCHES.md); `sync_upstream.py --patches` and the macOS CI check that the list is complete. Add new macOS runtime dependencies to `requirements-macos.txt` or the vendored package metadata, and guard new Win32-only imports.

## License and credits

This repository includes the **GNU Affero General Public License, version 3**; see [LICENSE.txt](LICENSE.txt) for its terms. Vendored components retain their own license notices.

Thanks to [ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves) and [ok-script](https://github.com/ok-oldking/ok-script) for the upstream projects. Game assets, names, and trademarks belong to Kuro Games.
