import os
import subprocess
from pathlib import Path


def test_failed_install_retries_and_dependency_changes_invalidate_stamp(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / 'run_macos.sh'
    script.write_text((root / 'run_macos.sh').read_text())
    (tmp_path / 'ok-script').mkdir()
    (tmp_path / 'ok-script/pyproject.toml').write_text('framework')
    (tmp_path / 'pyproject.toml').write_text('app')
    (tmp_path / 'requirements-macos.txt').write_text('mac packages')
    bin_dir = tmp_path / '.venv/bin'
    bin_dir.mkdir(parents=True)
    python = bin_dir / 'python'
    python.write_text('''#!/bin/sh
case "$*" in
  *"-m pip install -r"*)
    echo install >> "$TEST_LOG"
    echo "$*" >> "$TEST_ARGUMENTS"
    if [ -f "$FAIL_INSTALL" ]; then exit 1; fi
    ;;
esac
exit 0
''')
    python.chmod(0o755)
    log = tmp_path / 'install.log'
    fail = tmp_path / 'fail'
    fail.touch()
    env = dict(os.environ, TEST_LOG=str(log), FAIL_INSTALL=str(fail), TEST_ARGUMENTS=str(tmp_path / "arguments.log"))
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
    (tmp_path / 'requirements-macos.txt').write_text('changed mac packages')
    assert launch().returncode == 0
    assert len(log.read_text().splitlines()) == 6


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

