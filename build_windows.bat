@echo off
setlocal

echo("")
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo("")
python -m pip install --upgrade pip
python -m pip install .[gui,dev]
echo("")
pyinstaller packaging\wildcat.spec
pause
