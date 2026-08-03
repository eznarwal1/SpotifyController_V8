@echo off
setlocal
cd /d "%~dp0"

set "COMPANION=%~dp0companion"
set "PYTHON=%COMPANION%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Run setup_and_run.bat first.
    pause
    exit /b 1
)

pushd "%COMPANION%"
"%PYTHON%" test_protocol.py
echo.
"%PYTHON%" test_serial.py
popd
pause
