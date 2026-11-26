import json
import os
import subprocess
import sys
from pathlib import Path


def test_failed_install_retries_and_dependency_changes_invalidate_stamp(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / 'run_macos.sh'
    script.write_text((root / 'run_macos.sh').read_text())
    (tmp_path / 'requirements-macos.txt').write_text((root / 'requirements-macos.txt').read_text())
    (tmp_path / 'macos_launch.py').write_text((root / 'macos_launch.py').read_text())
    (tmp_path / 'ok-script').mkdir()
    (tmp_path / 'ok-script/setup.py').touch()
    (tmp_path / 'main.py').touch()
    (tmp_path / 'main_web.py').write_text('''
import json
import sys
from pathlib import Path
from pyappify import standalone
Path('relaunch.json').write_text(json.dumps(standalone.relaunch_info()))
Path('web-args.json').write_text(json.dumps(sys.argv[1:]))
''')
    (tmp_path / 'ok-script/pyproject.toml').write_text('framework')
    (tmp_path / 'pyproject.toml').write_text('app')
    bin_dir = tmp_path / '.venv/bin'
    bin_dir.mkdir(parents=True)
    python = bin_dir / 'python'
    python.write_text('''#!/bin/sh
case "$*" in
  *"-m pip install -r"*)
    echo install >> "$TEST_LOG"
    if [ -f "$FAIL_INSTALL" ]; then exit 1; fi
    ;;
  *"-m pip install -e"*)
    echo "$*" >> "$TEST_ARGUMENTS"
    ;;
  *"macos_launch.py"*)
    exec "$TEST_PYTHON" "$@"
    ;;
esac
exit 0
''')
    python.chmod(0o755)
    log = tmp_path / 'install.log'
    fail = tmp_path / 'fail'
    fail.touch()
    env = dict(os.environ, TEST_LOG=str(log), FAIL_INSTALL=str(fail),
               TEST_ARGUMENTS=str(tmp_path / 'arguments.log'), TEST_PYTHON=sys.executable)
    def launch(*args):
        return subprocess.run(['zsh', str(script), *args], env=env, capture_output=True)
    assert launch().returncode != 0
    stamp = tmp_path / '.venv/.macos-dependencies'
    assert not stamp.exists()
    fail.unlink()
    assert launch().returncode == 0
    assert stamp.exists()
    assert launch().returncode == 0
    assert log.read_text().splitlines() == ['install', 'install']
    (tmp_path / 'ok-script/pyproject.toml').write_text('changed framework')
    assert launch().returncode == 0
    assert len(log.read_text().splitlines()) == 3
    assert launch('--web').returncode == 0
    assert '[default,ocr,qt,web]' in (tmp_path / 'arguments.log').read_text().splitlines()[-1]
    assert launch('--web').returncode == 0
    assert len(log.read_text().splitlines()) == 4
    assert launch().returncode == 0
    assert len(log.read_text().splitlines()) == 5
    # The in-app updater installs requirements-macos.txt, so it is part of the stamp.
    (tmp_path / 'requirements-macos.txt').write_text('changed requirements')
    assert launch().returncode == 0
    assert len(log.read_text().splitlines()) == 6

    # A checkout with only a changed vendored manifest leaves PyAppify's
    # requirements file unchanged. Its recorded restart must still run setup.
    assert launch('--web', 'example').returncode == 0
    assert len(log.read_text().splitlines()) == 7
    relaunch = json.loads((tmp_path / 'relaunch.json').read_text())
    assert Path(relaunch['argv'][1]).name == 'macos_launch.py'
    (tmp_path / 'ok-script/pyproject.toml').write_text('changed by update')
    restarted = subprocess.run(relaunch['argv'], cwd=relaunch['cwd'], capture_output=True,
                               env=dict(env, PYTHONPATH=relaunch['pythonpath']))
    assert restarted.returncode == 0, restarted.stderr.decode()
    assert len(log.read_text().splitlines()) == 8
    assert json.loads((tmp_path / 'web-args.json').read_text()) == ['example']


def test_in_app_updater_installs_the_macos_requirements():
    # A checkout updates with the first pyappify.yml profile unless
    # PYAPPIFY_APP_PROFILE names one; requirements.txt has Windows-only pins.
    from pyappify import standalone

    root = Path(__file__).resolve().parents[1]
    profiles = standalone.parse_profiles((root / 'pyappify.yml').read_text())
    for name in (None, 'macOS'):
        profile = standalone.select_profile(profiles, name)
        assert profile['name'] == 'macOS'
        assert profile['requirements'] == 'requirements-macos.txt'
        assert '--no-deps' not in profile['pip_args']
    requirements = [line for line in (root / 'requirements-macos.txt').read_text().splitlines()
                    if line and not line.startswith('#')]
    assert not any('pywin32' in line for line in requirements)
    assert '-e ./ok-script[default,ocr,qt]' in requirements
    assert "os.environ['PYAPPIFY_APP_PROFILE'] = 'macOS'" in (root / 'macos_launch.py').read_text()


def test_macos_app_window_initialization():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from config import config
    from ok import OK

    ok = OK(config)
    try:
        ok.app.show_main_window()
        assert ok.app.main_window is not None
        assert ok.app.main_window.tasks_page is not None
        assert ok.app.main_window.isVisible()
    finally:
        if ok.app.main_window is not None:
            ok.app.main_window.dispose()
        ok.quit()

