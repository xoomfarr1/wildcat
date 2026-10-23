@echo off
setlocal

echo("")
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo("")
python -m pip install --upgrade pip
python -m pip install PySide6 PyInstaller python-can pydantic pyserial requests loguru
echo("")
pyinstaller packaging\wildcat.spec
pause
