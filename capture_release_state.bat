@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY=companion\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" tools\release_sync.py capture
pause
