from __future__ import annotations

from typing import Any, Awaitable, Callable

from protocol import make_state_message
from serial_manager import SerialManager
from spotify_controller import SpotifyController
from ui_state import AppState
from volume_controller import VolumeController
from v8_controller import V8Controller


QueueWindowUpdater = Callable[
    [SpotifyController, AppState, V8Controller],
    tuple[list[str], int],
]
PreviousViewResolver = Callable[[V8Controller], str]
LogFn = Callable[[str], None]


async def process_display_command(
    message: dict[str, Any] | None,
    spotify: SpotifyController,
    volume: VolumeController,
    state: AppState,
    serial_manager: SerialManager,
    v8: V8Controller,
    *,
    update_queue_window: QueueWindowUpdater,
    previous_view: PreviousViewResolver,
    send_current_state: Callable[..., Awaitable[None]],
    queue_follow_state: Any,
    log: LogFn,
) -> None:
    if not isinstance(message, dict):
        return

    command = message.get("command")
    if not isinstance(command, str):
        return

    command = command.strip().lower()

    if command == "view_next":
        selected_view = v8.next_view()
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
        selected_view = previous_view(v8)
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
        v8.now_playing()
        state.view_mode = "now_playing"
        log("V8 view changed to: now_playing")
        await send_current_state(
            spotify,
            volume,
            state,
            serial_manager,
        )
        return

    if command == "queue_home":
        if v8.state.view == "queue":
            v8.state.queue_index = 0
            queue_follow_state.manual_navigation = False
            queue_follow_state.selected_track = ""
            update_queue_window(spotify, state, v8)

            if serial_manager.is_connected:
                await _send_state(serial_manager, state)

            log("Queue selection returned to beginning.")
        return

    if command in ("utility_previous", "utility_next"):
        if v8.state.view == "queue":
            queue = spotify._chrome_bridge.selected_or_playing_queue()

            if queue:
                direction = -1 if command == "utility_previous" else 1
                queue_follow_state.manual_navigation = True
                v8.state.queue_index = max(
                    0,
                    min(
                        v8.state.queue_index + direction,
                        len(queue) - 1,
                    ),
                )
                update_queue_window(spotify, state, v8)

                if serial_manager.is_connected:
                    await _send_state(serial_manager, state)
            return

        v8.move_selection(
            -1 if command == "utility_previous" else 1
        )
        return

    if command == "utility_select":
        if v8.state.view == "queue":
            queue = spotify._chrome_bridge.selected_or_playing_queue()

            if queue:
                queue_index = max(
                    0,
                    min(v8.state.queue_index, len(queue) - 1),
                )
                success = spotify._chrome_bridge.activate_queue_item(
                    queue_index
                )

                if success:
                    queue_follow_state.manual_navigation = False
                    queue_follow_state.selected_track = ""

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
                queue = spotify._chrome_bridge.selected_or_playing_queue()

                if queue:
                    direction = -1 if command == "previous" else 1
                    queue_follow_state.manual_navigation = True
                    v8.state.queue_index = max(
                        0,
                        min(
                            v8.state.queue_index + direction,
                            len(queue) - 1,
                        ),
                    )
                    update_queue_window(spotify, state, v8)

                    if serial_manager.is_connected:
                        await _send_state(serial_manager, state)
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


async def _send_state(
    serial_manager: SerialManager,
    state: AppState,
) -> None:
    import asyncio

    await asyncio.to_thread(
        serial_manager.send_line,
        make_state_message(state),
    )
