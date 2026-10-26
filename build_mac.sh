#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root regardless of invocation directory.
cd "$(dirname "$0")"

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
python -m PyInstaller \
    --onefile \
    --windowed \
    --name wildcat \
    --paths src \
    --hidden-import PySide6.QtCore \
    --hidden-import PySide6.QtGui \
    --hidden-import PySide6.QtWidgets \
    src/wildcat/gui/app.py
