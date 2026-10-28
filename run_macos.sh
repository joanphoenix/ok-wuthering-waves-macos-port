#!/usr/bin/env zsh
set -e

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

# Publish the fingerprint only after installation succeeds. Interrupted installs
# retry on the next launch; dependency and launcher changes invalidate it.
INSTALL_STAMP="$SCRIPT_DIR/.venv/.macos-dependencies"
INSTALL_KEY=$(shasum -a 256 "$SCRIPT_DIR/run_macos.sh" "$SCRIPT_DIR/ok-script/pyproject.toml" "$SCRIPT_DIR/pyproject.toml" | shasum -a 256)
if [[ ! -f "$INSTALL_STAMP" ]] || [[ "$(cat "$INSTALL_STAMP")" != "$INSTALL_KEY" ]]; then
    "$PYTHON_BIN" -m pip install --upgrade pip
    OK_SCRIPT_BUILD_VERSION=2.0.17+macos.1 "$PYTHON_BIN" -m pip install -e "$SCRIPT_DIR/ok-script[default,ocr,qt,web]" \
        pyobjc-framework-Quartz pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices \
        onnxruntime opencv-python polib 'mcp==2.3.0'
    print -r -- "$INSTALL_KEY" > "$INSTALL_STAMP"
fi

export PYTHONPATH="$SCRIPT_DIR/ok-script:$SCRIPT_DIR:${PYTHONPATH:-}"

case "${1:-}" in
    --web)
        shift
        exec "$PYTHON_BIN" main_web.py "$@"
        ;;
    --debug)
        shift
        exec "$PYTHON_BIN" main_debug.py "$@"
        ;;
    *)
        exec "$PYTHON_BIN" main.py "$@"
        ;;
esac
