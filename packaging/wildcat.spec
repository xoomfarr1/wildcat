# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Wildcat."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

REPO = Path.cwd()  # PyInstaller spec namespace lacks __file__; run from repo root
block_cipher = None


def dependency_hook():
    return (
        collect_submodules("can")
        + collect_submodules("pydantic")
        + collect_submodules("PySide6")
    )


hiddenimports = dependency_hook()

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
    [],
    exclude_binaries=True,
    name="wildcat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="wildcat",
)
