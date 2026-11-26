#!/usr/bin/env zsh
set -e
set -o pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Setting up Python virtual environment in $SCRIPT_DIR/.venv ..."
    if command -v python3.12 >/dev/null 2>&1; then
        SETUP_PYTHON=python3.12
    else
        SETUP_PYTHON=python3
    fi
    "$SETUP_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else "Python 3.12 is required")'
    "$SETUP_PYTHON" -m venv "$SCRIPT_DIR/.venv"
fi
"$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else "Recreate .venv with Python 3.12")'
if [[ "${1:-}" != "--prepare-only" ]]; then
    exec "$PYTHON_BIN" "$SCRIPT_DIR/macos_launch.py" "$@"
fi
shift

# Publish the fingerprint only after installation succeeds. Interrupted installs
# retry on the next launch; dependency and launcher changes invalidate it.
EXTRAS="default,ocr,qt"
if [[ "${1:-}" == "--web" ]]; then
    EXTRAS="$EXTRAS,web"
fi
INSTALL_STAMP="$SCRIPT_DIR/.venv/.macos-dependencies"
INSTALL_KEY="$EXTRAS:$(shasum -a 256 run_macos.sh requirements-macos.txt \
    ok-script/setup.py ok-script/pyproject.toml pyproject.toml | shasum -a 256)"
export OK_SCRIPT_BUILD_VERSION=3.0.15b1+macos.1
if [[ ! -f "$INSTALL_STAMP" ]] || [[ "$(cat "$INSTALL_STAMP")" != "$INSTALL_KEY" ]]; then
    "$PYTHON_BIN" -m pip install --upgrade pip
    # The in-app updater installs the same file (see pyappify.yml).
    "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements-macos.txt"
    if [[ "$EXTRAS" != "default,ocr,qt" ]]; then
        "$PYTHON_BIN" -m pip install -e "$SCRIPT_DIR/ok-script[$EXTRAS]"
    fi
    print -r -- "$INSTALL_KEY" > "$INSTALL_STAMP"
fi
