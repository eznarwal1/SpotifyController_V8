@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "COMPANION=%~dp0companion"
set "VENV=%COMPANION%\.venv"
set "PYTHON=%VENV%\Scripts\python.exe"

if not exist "%COMPANION%\main.py" (
    echo ERROR: companion\main.py was not found.
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo Creating the Python virtual environment...

    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3.12 -m venv "%VENV%"
        if errorlevel 1 py -3 -m venv "%VENV%"
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo ERROR: Python 3 was not found.
            echo Install Python 3.12 and run this file again.
            pause
            exit /b 1
        )
        python -m venv "%VENV%"
    )

    if not exist "%PYTHON%" (
        echo ERROR: Virtual environment creation failed.
        pause
        exit /b 1
    )
)

echo Installing or updating dependencies...
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :failure

"%PYTHON%" -m pip install -r "%COMPANION%\requirements.txt"
if errorlevel 1 goto :failure

echo.
echo Running Python import checks...
pushd "%COMPANION%"
"%PYTHON%" -c "import main, protocol, serial_manager, spotify_controller, metadata_renderer, v8_controller, v8_renderer; print('Import checks passed.')"
if errorlevel 1 (
    popd
    goto :failure
)

echo.
echo Starting Universal Media Controller V8...
echo Press Ctrl+C to stop.
echo.
"%PYTHON%" -u main.py
set "EXITCODE=%ERRORLEVEL%"
popd

echo.
echo Controller exited with code %EXITCODE%.
pause
exit /b %EXITCODE%

:failure
echo.
echo SETUP FAILED. Read the error above.
pause
exit /b 1
