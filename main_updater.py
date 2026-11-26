"""Open the PyAppify update manager for this checkout."""

if __name__ == '__main__':
    import os
    import sys
    from pathlib import Path

    if sys.platform == 'darwin':
        # Install requirements-macos.txt on update (pyappify.yml's macOS profile).
        os.environ.setdefault('PYAPPIFY_APP_PROFILE', 'macOS')

    from pyappify.updater_ui import main

    sys.exit(main(['--repo', str(Path(__file__).resolve().parent), *sys.argv[1:]]))
