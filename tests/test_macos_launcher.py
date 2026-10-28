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
    bin_dir = tmp_path / '.venv/bin'
    bin_dir.mkdir(parents=True)
    python = bin_dir / 'python'
    python.write_text('''#!/bin/sh
case "$*" in
  *"-m pip install -e"*)
    echo install >> "$TEST_LOG"
    if [ -f "$FAIL_INSTALL" ]; then exit 1; fi
    ;;
esac
exit 0
''')
    python.chmod(0o755)
    log = tmp_path / 'install.log'
    fail = tmp_path / 'fail'
    fail.touch()
    env = dict(os.environ, TEST_LOG=str(log), FAIL_INSTALL=str(fail))
    def launch():
        return subprocess.run(['zsh', str(script)], env=env, capture_output=True)
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
