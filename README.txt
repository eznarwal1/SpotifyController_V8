Spotify Controller V6 Stable
============================

Folder layout
-------------
SpotifyController_V6_Stable/
├── companion/
├── firmware/
├── docs/
├── tools/
├── setup_and_run.bat
├── run_debug.bat
├── run_tests.bat
├── install_startup.ps1
└── remove_startup.ps1

First run
---------
1. Extract the entire folder.
2. Double-click setup_and_run.bat.
3. The script creates companion\.venv, installs dependencies, and starts main.py.
4. Keep PlatformIO Serial Monitor closed while the companion is running.

Later debug runs
----------------
Double-click run_debug.bat.

Automatic startup
-----------------
After setup_and_run.bat has completed:

1. Open PowerShell in this folder.
2. Run:

   Get-ChildItem *.ps1 | Unblock-File
   .\install_startup.ps1


Firmware
--------
No firmware files were supplied in the latest upload, so the firmware folder is
included as a placeholder. Continue using the working V5/V6 Protocol 2 firmware
at 2,000,000 baud.
