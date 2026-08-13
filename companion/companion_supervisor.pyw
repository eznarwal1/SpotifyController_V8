from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import os
import subprocess
import sys
import time
import logging

COMPANION_DIR = Path(__file__).resolve().parent
MAIN = COMPANION_DIR / "main.py"
PYTHON = COMPANION_DIR / ".venv" / "Scripts" / "python.exe"
LOG = COMPANION_DIR / "companion_autostart.log"
PID_FILE = COMPANION_DIR / "companion_autostart.pid"

MUTEX_NAME = r"Local\SpotifyControllerCompanionSupervisor"
ERROR_ALREADY_EXISTS = 183

CREATE_NEW_CONSOLE = 0x00000010
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0


def log(message: str) -> None:
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception as exc:
        logging.debug("companion_supervisor: log write failed: %s", exc)


def acquire_single_instance() -> object | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return None

    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None

    return handle


def hidden_console_startupinfo() -> subprocess.STARTUPINFO:
    info = subprocess.STARTUPINFO()
    info.dwFlags |= STARTF_USESHOWWINDOW
    info.wShowWindow = SW_HIDE
    return info


def run() -> int:
    mutex = acquire_single_instance()
    if mutex is None:
        return 0

    if not MAIN.exists():
        log(f"ERROR: main.py missing: {MAIN}")
        return 2

    python_exe = PYTHON if PYTHON.exists() else Path(sys.executable)

    try:
        PID_FILE.write_text(str(os.getpid()), encoding="ascii")
    except Exception as exc:
        logging.debug("companion_supervisor: failed to write pid file: %s", exc)

    log("Supervisor started.")
    log(f"Python: {python_exe}")
    log(f"Main: {MAIN}")

    try:
        while True:
            try:
                child = subprocess.Popen(
                    [str(python_exe), str(MAIN)],
                    cwd=str(COMPANION_DIR),
                    creationflags=CREATE_NEW_CONSOLE,
                    startupinfo=hidden_console_startupinfo(),
                )
            except Exception as exc:
                log(
                    "Could not start companion: "
                    f"{type(exc).__name__}: {exc}"
                )
                time.sleep(5.0)
                continue

            log(f"Companion started, PID={child.pid}.")
            exit_code = child.wait()
            log(f"Companion exited with code {exit_code}; restarting in 5s.")
            time.sleep(5.0)
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception as exc:
            logging.debug("companion_supervisor: failed to remove pid file: %s", exc)


if __name__ == "__main__":
    raise SystemExit(run())
