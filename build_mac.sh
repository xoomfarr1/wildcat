#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root regardless of invocation directory.
cd "$(dirname "$0")"

# Usage:
#   ./build_mac.sh          -> normal windowed .app (no console)
#   DEBUG=1 ./build_mac.sh  -> console build that prints the startup traceback
DEBUG="${DEBUG:-0}"

# Create venv if missing.
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

# Activate venv.
source .venv/bin/activate

# Upgrade pip and install project with gui + dev extras.
python -m pip install --upgrade pip
python -m pip install ".[gui,dev]"

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
    python -m PyInstaller --console "${COMMON[@]}"
else
    python -m PyInstaller --windowed "${COMMON[@]}"
fi
