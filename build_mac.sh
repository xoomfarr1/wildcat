#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root regardless of invocation directory.
cd "$(dirname "$0")"

# Usage:
#   ./build_mac.sh          -> normal windowed .app (no console)
#   DEBUG=1 ./build_mac.sh  -> console build that prints the startup traceback
DEBUG="${DEBUG:-0}"

# Ensure uv is available.
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found; installing via pip..." >&2
    python3 -m pip install --quiet uv
fi

# Create/sync venv with uv (uses uv.lock for reproducibility).
uv sync --extra dev

# Build standalone macOS app bundle.
COMMON=(
    --onefile
    --name wildcat
    --paths src
    --hidden-import PySide6.QtCore
    --hidden-import PySide6.QtGui
    --hidden-import PySide6.QtWidgets
    --osx-bundle-identifier com.wildcat.diagnostics
    --collect-all PySide6
    src/wildcat/gui/app.py
)

if [ "$DEBUG" = "1" ]; then
    # Keep a console so a startup crash prints its traceback instead of just
    # flashing the logo and exiting.
    uv run python -m PyInstaller --console "${COMMON[@]}"
else
    uv run python -m PyInstaller --windowed "${COMMON[@]}"
fi
