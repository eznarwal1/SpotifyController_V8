@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0companion\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo The V8 virtual environment has not been created.
    echo Run setup_and_run.bat first.
    pause
    exit /b 1
)

pushd "%~dp0companion"
"%PYTHON%" -u main.py
set "EXITCODE=%ERRORLEVEL%"
popd

echo.
echo Controller exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
