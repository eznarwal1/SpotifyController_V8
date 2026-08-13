from __future__ import annotations

import asyncio
from collections.abc import Callable

from serial_manager import SerialManager
from spotify_controller import SpotifyController
from system_status import get_battery_status
from ui_state import AppState, MediaState
from volume_controller import VolumeController

from v9.state_sender import reset_state_sender, send_state_if_changed

LogFn = Callable[[str], None]
DisplayFn = Callable[[AppState], None]


async def update_state(
    spotify: SpotifyController,
    volume: VolumeController,
    state: AppState,
) -> None:
    media = await spotify.get_state()

    if media is None:
        state.spotify_connected = False
        state.media = MediaState()
    else:
        state.spotify_connected = True
        state.media = media

    state.volume = volume.get_volume()
    state.muted = volume.is_muted()

    (
        state.discord_call_active,
        state.discord_muted,
        state.discord_deafened,
    ) = spotify.get_discord_status()

    battery = get_battery_status()
    state.battery_present = battery.present
    state.battery_percent = battery.percent
    state.battery_charging = battery.charging


async def send_current_state(
    spotify: SpotifyController,
    volume: VolumeController,
    state: AppState,
    serial_manager: SerialManager,
    delay_seconds: float = 0.0,
) -> None:
    if delay_seconds:
        await asyncio.sleep(delay_seconds)

    await update_state(spotify, volume, state)

    await send_state_if_changed(
        serial_manager,
        state,
    )


async def polling_loop(
    spotify: SpotifyController,
    volume: VolumeController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    *,
    log: LogFn,
    display_state: DisplayFn,
) -> None:
    last_connected: bool | None = None

    while not stop_event.is_set():
        try:
            await update_state(spotify, volume, state)
            state.display_connected = serial_manager.is_connected
            state.display_port = serial_manager.port_name or ""

            if state.display_connected != last_connected:
                log(
                    "Display connection changed: "
                    f"connected={state.display_connected}, "
                    f"port={state.display_port!r}"
                )
                last_connected = state.display_connected

            if serial_manager.is_connected:
                await send_state_if_changed(
                    serial_manager,
                    state,
                )
            else:
                reset_state_sender(serial_manager)

            display_state(state)

        except Exception as exc:
            log(
                f"Polling loop error: "
                f"{type(exc).__name__}: {exc}"
            )

        await asyncio.sleep(1.0)
