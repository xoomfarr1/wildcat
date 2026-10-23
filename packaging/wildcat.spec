# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Wildcat -- standalone Windows GUI executable.

Modeled on the proven mbtools spec: ONE standalone exe (onefile), the Qt
modules listed explicitly, and PyInstaller's official PySide6 hooks collecting
the Qt C++ binaries + data automatically. Run from the repository root:

    pyinstaller packaging\\wildcat.spec

The result is a single packaging\\dist\\wildcat.exe.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

REPO = Path.cwd()  # PyInstaller spec namespace lacks __file__; run from repo root
block_cipher = None

# PySide6: the GUI imports QtWidgets, which transitively needs QtCore + QtGui.
# List them explicitly so PyInstaller's official PySide6 hooks fire and pull in
# the Qt .pyd/.dll binaries, plugins, translations, styles and image formats.
#
# Do NOT collect_submodules("PySide6"): it is a known anti-pattern that both
# grinds the build to a halt and breaks the frozen app with
# "ModuleNotFoundError: No module named 'PySide6'".
QT_MODULES = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

hiddenimports = (
    collect_submodules("can")
    + collect_submodules("pydantic")
    + QT_MODULES
)

a = Analysis(
    [str(REPO / "src" / "wildcat" / "gui" / "app.py")],
    pathex=[str(REPO / "src")],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="wildcat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # no UPX: never mangle the Qt binaries
    console=False,                   # windowed app: no terminal window
    onefile=True,                    # single standalone exe (matches mbtools)
    runtime_tmpdir=None,
    argv_emulation=False,
)
