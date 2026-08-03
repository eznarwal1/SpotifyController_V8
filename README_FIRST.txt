Universal Media Controller V8 — Complete Test Release
=====================================================

This package is intended to be installed as a separate test copy. Do not
overwrite your working V7 folder until V8 has been tested.

1. PREPARE A TEST COPY
----------------------
Make a copy of your entire current working project folder and name it:

    UniversalMediaController_V8_Test

Keep the original working folder unchanged.

2. COMPANION INSTALLATION
-------------------------
Replace the copied project's companion folder contents with every file from:

    companion\

Then double-click:

    setup_and_run.bat

The launcher creates companion\.venv, installs the dependencies, checks the
Python imports, and starts the companion. It remains open if an error occurs.

For later runs, use:

    run_debug.bat

3. FIRMWARE INSTALLATION
------------------------
Copy every file from:

    firmware_replacements\

into the copied PlatformIO project's src folder, replacing matching files.

Keep the other working firmware files that are not included here, including
the display driver, DisplayManager, Artwork, and Controls files.

In PlatformIO:

    Clean
    Build
    Upload

The V8 firmware uses Protocol 2 at 2,000,000 baud.

4. CHROME EXTENSION
-------------------
Open:

    chrome://extensions

Remove the older unpacked controller extension. Enable Developer mode, choose
Load unpacked, and select:

    chrome_extension\

Refresh Discord Web and all browser media tabs after loading it.

5. V8 DISPLAY NAVIGATION
------------------------
Tap View to cycle through:

    Now Playing
    Queue
    Mixer
    Notifications
    Dashboard
    Themes

Long-press View to return to Now Playing.

Inside a V8 page:

    Previous / Next   Move selection
    Play / Pause      Activate selection
    Encoder volume    Change selected app volume in Mixer

6. INCLUDED FEATURES
--------------------
- Windows desktop media sessions
- Individual Chrome media tabs
- Unicode metadata and source selector rendered on Windows
- Correct rounded source-button corners
- Discord Web call status, mute, and deafen
- Battery percentage and charging status
- Read-only YouTube and Spotify Web queue page
- Per-application Windows volume mixer
- Discord/battery notification page
- CPU, RAM, power, and network dashboard
- Modern, OLED, Minimal, and Retro V8 page themes

7. CURRENT TEST-RELEASE LIMITATIONS
-----------------------------------
- Queue items are displayed but cannot yet be selected to start playback.
- Website controls can break if a site's page structure changes.
- Themes apply to the PC-rendered V8 pages, not every native LVGL control.
- Notifications currently focus on Discord calls and battery warnings.
- The package has passed Python syntax/import preparation checks here, but the
  firmware must still be compiled against your exact PlatformIO libraries and
  tested on your display hardware.
