"""Start the selected macOS entry point after checking launcher dependencies."""

import os
from pathlib import Path
import runpy
import subprocess
import sys


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    scripts = {
        '--web': 'main_web.py',
        '--debug': 'main_debug.py',
        '--updater': 'main_updater.py',
    }
    args = sys.argv[1:]
    mode = args[0] if args and args[0] in scripts else None
    # PyAppify replays the original Python command after checkout. Run the same
    # dependency check on that restart, including the web extras when needed.
    prepare = ['zsh', str(root / 'run_macos.sh'), '--prepare-only']
    if mode:
        prepare.append(mode)
    result = subprocess.run(prepare, cwd=root)
    if result.returncode:
        sys.exit(result.returncode)

    os.chdir(root)
    vendor = str(root / 'ok-script')
    sys.path.insert(0, vendor)
    inherited = os.environ.get('PYTHONPATH', '').split(os.pathsep)
    os.environ['PYTHONPATH'] = os.pathsep.join(dict.fromkeys([vendor, str(root), *filter(None, inherited)]))
    os.environ['PYAPPIFY_APP_PROFILE'] = 'macOS'
    script = root / scripts.get(mode, 'main.py')
    sys.argv = [str(script), *(args[1:] if mode else args)]
    runpy.run_path(str(script), run_name='__main__')
