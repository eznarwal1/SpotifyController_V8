from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from serial_manager import SerialManager
from spotify_controller import SpotifyController
from ui_state import AppState
from v8_controller import V8Controller
from v9.navigation_bridge import V8ViewNavigator
from v9.queue_controller import QueueController
from v9.state_sender import send_state_if_changed
from volume_controller import VolumeController

LogFn = Callable[[str], None]


async def process_display_command(
    message: dict[str, Any] | None,
    spotify: SpotifyController,
    volume: VolumeController,
    state: AppState,
    serial_manager: SerialManager,
    v8: V8Controller,
    *,
    view_navigator: V8ViewNavigator,
    send_current_state: Callable[..., Awaitable[None]],
    queue_controller: QueueController,
    log: LogFn,
) -> None:
    if not isinstance(message, dict):
        return

    command = message.get("command")
    if not isinstance(command, str):
        return

    command = command.strip().lower()

    if command == "view_next":
        selected_view = view_navigator.next()
        state.view_mode = selected_view
        log(f"V8 view changed to: {selected_view}")
        await send_current_state(
            spotify,
            volume,
            state,
            serial_manager,
        )
        return

    if command == "view_previous":
        selected_view = view_navigator.previous()
        state.view_mode = selected_view
        log(f"V8 view changed backward to: {selected_view}")
        await send_current_state(
            spotify,
            volume,
            state,
            serial_manager,
        )
        return

    if command == "view_now_playing":
        selected_view = view_navigator.home()
        state.view_mode = selected_view
        log(f"V8 view changed to: {selected_view}")
        await send_current_state(
            spotify,
            volume,
            state,
            serial_manager,
        )
        return

    if command == "queue_home":
        if v8.state.view == "queue":
            queue_controller.home()

            if serial_manager.is_connected:
                await send_state_if_changed(serial_manager, state)

            log("Queue selection returned to beginning.")
        return

    if command in ("utility_previous", "utility_next"):
        if v8.state.view == "queue":
            direction = -1 if command == "utility_previous" else 1
            changed = queue_controller.move(direction)

            if changed and serial_manager.is_connected:
                await send_state_if_changed(serial_manager, state)
            return

        v8.move_selection(
            -1 if command == "utility_previous" else 1
        )
        return

    if command == "utility_select":
        if v8.state.view == "queue":
            success, queue_index = queue_controller.select_current()

            log(
                "Queue selection "
                f"{queue_index}: "
                f"{'sent' if success else 'unavailable'}"
            )
            return

        result = v8.activate()
        log(f"V8 action: {result}")
        return

    if command == "mixer_volume_down":
        v8.change_volume(-5)
        return

    if command == "mixer_volume_up":
        v8.change_volume(5)
        return

    if command == "mixer_mute":
        if v8.state.view == "mixer":
            v8.activate()
        return

    if v8.state.view != "now_playing":
        if command in ("previous", "next"):
            if v8.state.view == "queue":
                direction = -1 if command == "previous" else 1
                changed = queue_controller.move(direction)

                if changed and serial_manager.is_connected:
                    await send_state_if_changed(serial_manager, state)
                return

            v8.move_selection(-1 if command == "previous" else 1)
            return

        if command == "play_pause":
            result = v8.activate()
            log(f"V8 action: {result}")
            return

        if command == "volume":
            amount = message.get("amount")
            if isinstance(amount, bool) or not isinstance(
                amount,
                (int, float),
            ):
                return

            if v8.change_volume(
                max(-10, min(10, int(amount)))
            ):
                return

    if command == "play_pause":
        success = await spotify.toggle_play_pause()
        delay = 0.0
    elif command == "previous":
        success = await spotify.previous_track()
        delay = 0.25
    elif command == "next":
        success = await spotify.next_track()
        delay = 0.25
    elif command == "shuffle":
        success = await spotify.toggle_shuffle()
        delay = 0.05
    elif command == "repeat":
        success = await spotify.cycle_repeat_mode()
        delay = 0.05
    elif command == "source":
        selected_source = await spotify.cycle_media_source()
        log(f"Selected media source: {selected_source}")
        success = True
        delay = 0.05
    elif command == "source_auto":
        spotify.use_automatic_source_selection()
        log("Selected media source: Auto")
        success = True
        delay = 0.05
    elif command == "discord_mute":
        success = spotify.toggle_discord_mute()
        delay = 0.15
    elif command == "discord_deafen":
        success = spotify.toggle_discord_deafen()
        delay = 0.15
    elif command == "volume":
        amount = message.get("amount")
        if isinstance(amount, bool) or not isinstance(
            amount,
            (int, float),
        ):
            return
        volume.change_volume(max(-10, min(10, int(amount))))
        success = True
        delay = 0.05
    elif command == "mute":
        volume.toggle_mute()
        success = True
        delay = 0.05
    else:
        return

    if success:
        await send_current_state(
            spotify,
            volume,
            state,
            serial_manager,
            delay_seconds=delay,
        )

