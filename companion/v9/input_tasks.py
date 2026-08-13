from __future__ import annotations

import asyncio
from collections.abc import Callable

from serial_manager import SerialManager
from spotify_controller import SpotifyController
from ui_state import AppState
from v8_controller import V8Controller
from v9.command_router import process_display_command
from v9.navigation_bridge import V8ViewNavigator
from v9.queue_controller import QueueController
from volume_controller import VolumeController

LogFn = Callable[[str], None]


async def serial_command_loop(
    spotify: SpotifyController,
    volume: VolumeController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    v8: V8Controller,
    view_navigator: V8ViewNavigator,
    queue_controller: QueueController,
    *,
    send_current_state,
    log: LogFn,
) -> None:
    while not stop_event.is_set():
        if not serial_manager.is_connected:
            await asyncio.sleep(0.25)
            continue

        try:
            message = await asyncio.to_thread(
                serial_manager.read_command
            )

            if isinstance(message, dict):
                await process_display_command(
                    message,
                    spotify,
                    volume,
                    state,
                    serial_manager,
                    v8,
                    view_navigator=view_navigator,
                    send_current_state=send_current_state,
                    queue_controller=queue_controller,
                    log=log,
                )

        except Exception as exc:
            log(
                "Serial command loop error: "
                f"{type(exc).__name__}: {exc}"
            )

        await asyncio.sleep(0.01)


async def command_loop(
    spotify: SpotifyController,
    volume: VolumeController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    *,
    send_current_state,
) -> None:
    while not stop_event.is_set():
        command = (
            await asyncio.to_thread(input, "\n> ")
        ).strip().lower()

        if command == "q":
            stop_event.set()
            continue

        if command == "p":
            success = await spotify.toggle_play_pause()
            delay = 0.0
        elif command == "b":
            success = await spotify.previous_track()
            delay = 0.25
        elif command == "n":
            success = await spotify.next_track()
            delay = 0.25
        elif command == "r":
            success = await spotify.cycle_repeat_mode()
            delay = 0.05
        elif command == "s":
            selected_source = await spotify.cycle_media_source()
            print(f"Selected source: {selected_source}")
            success = True
            delay = 0.05
        elif command == "a":
            spotify.use_automatic_source_selection()
            print("Selected source: Auto")
            success = True
            delay = 0.05
        elif command == "+":
            volume.change_volume(2)
            success = True
            delay = 0.05
        elif command == "-":
            volume.change_volume(-2)
            success = True
            delay = 0.05
        elif command == "m":
            volume.toggle_mute()
            success = True
            delay = 0.05
        else:
            print("Use p, b, n, r, s, a, +, -, m, or q.")
            continue

        if success:
            await send_current_state(
                spotify,
                volume,
                state,
                serial_manager,
                delay_seconds=delay,
            )
