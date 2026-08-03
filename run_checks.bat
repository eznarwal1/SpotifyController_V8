@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0companion\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Run setup_and_run.bat first.
    pause
    exit /b 1
)

pushd "%~dp0companion"
"%PYTHON%" -m py_compile *.py
if errorlevel 1 (
    popd
    echo Python compile check failed.
    pause
    exit /b 1
)

"%PYTHON%" test_protocol.py
echo.
"%PYTHON%" test_serial.py
popd
pause
