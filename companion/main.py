from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import threading

from serial_manager import SerialManager
from spotify_controller import SpotifyController
from ui_state import AppState
from volume_controller import VolumeController
from v8_controller import V8Controller
from v8_renderer import WIDTH as VIEW_WIDTH, HEIGHT as VIEW_HEIGHT, render_view
from v9.mixer_model import build_mixer_state
from v9.command_router import process_display_command
from v9.navigation_bridge import V8ViewNavigator
from v9.queue_controller import QueueController
from v9.runtime_state import polling_loop, send_current_state
from v9.media_tasks import artwork_loop, metadata_image_loop, source_image_loop
from v9.state_sender import send_state_if_changed, reset_state_sender


DEBUG_LOG = Path(__file__).with_name("debug.log")
_log_lock = threading.Lock()


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {message}"

    with _log_lock:
        try:
            with DEBUG_LOG.open("a", encoding="utf-8", buffering=1) as file:
                file.write(line + "\n")
                file.flush()
        except OSError:
            pass

    print(line, flush=True)


def reset_log() -> None:
    try:
        DEBUG_LOG.write_text(
            f"Debug session started {datetime.now().isoformat()}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def format_time(seconds: int) -> str:
    minutes, remaining = divmod(max(0, seconds), 60)
    return f"{minutes}:{remaining:02d}"


def display_state(state: AppState) -> None:
    print("\nUniversal Media Controller")
    print("------------------")

    if state.spotify_connected:
        print(f"Title:       {state.media.title}")
        print(f"Artist:      {state.media.artist}")
        print(f"Album:       {state.media.album or 'Unknown'}")
        print(f"Source:      {state.media.application or 'Unknown'}")
        print(f"State:       {state.media.playback_status}")
        print(
            f"Shuffle:     "
            f"{'On' if state.media.shuffle_active else 'Off'}"
        )
        print(f"Repeat:      {state.media.repeat_mode}")
        print(
            f"Position:    {format_time(state.media.position_seconds)} / "
            f"{format_time(state.media.duration_seconds)}"
        )
    else:
        print("Media:       Not connected")

    print(f"Volume:      {state.volume}%")
    print(f"Muted:       {'Yes' if state.muted else 'No'}")
    print(
        "Display:     "
        + (
            state.display_port
            if state.display_connected
            else "Not connected"
        )
    )
    print("Commands: p, b, n, r, s, a, +, -, m, q")


async def serial_command_loop(
    spotify: SpotifyController,
    volume: VolumeController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    v8: V8Controller,
    view_navigator: V8ViewNavigator,
    queue_controller: QueueController,
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
                f"Serial command loop error: "
                f"{type(exc).__name__}: {exc}"
            )

        await asyncio.sleep(0.01)


async def command_loop(
    spotify: SpotifyController,
    volume: VolumeController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
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


async def v8_view_loop(
    spotify: SpotifyController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    v8: V8Controller,
    view_navigator: V8ViewNavigator,
    queue_controller: QueueController,
) -> None:
    last_render_key: tuple | None = None

    while not stop_event.is_set():
        view = view_navigator.current
        state.view_mode = view
        state.notification_text = ""

        v8.notifications.update_status(
            discord_call=state.discord_call_active,
            battery_present=state.battery_present,
            battery_percent=state.battery_percent,
            battery_charging=state.battery_charging,
        )

        if view == "now_playing":
            last_render_key = None
            await asyncio.sleep(0.25)
            continue

        queue, _queue_selected = queue_controller.refresh_window()
        (
            queue_source,
            queue_available,
            queue_status,
        ) = spotify._chrome_bridge.selected_queue_status()

        # V9 Queue is rendered locally by LVGL. Do not transmit the legacy
        # utility-page bitmap while this page is active.
        if view == "queue":
            last_render_key = None
            await asyncio.sleep(0.25)
            continue

        mixer = v8.mixer.sessions()
        native_mixer = build_mixer_state(
            mixer,
            selected_index=v8.state.mixer_index,
        )
        state.mixer_entries = [
            entry.name
            for entry in native_mixer.entries
        ]
        state.mixer_volumes = [
            entry.volume
            for entry in native_mixer.entries
        ]
        state.mixer_muted = [
            entry.muted
            for entry in native_mixer.entries
        ]
        state.mixer_selected_index = native_mixer.selected_index

        # V9 Mixer is rendered locally by LVGL. Do not transmit the legacy
        # utility-page bitmap while this page is active.
        if view == "mixer":
            last_render_key = None
            await asyncio.sleep(0.35)
            continue
        notifications = [
            item.text
            for item in v8.notifications.active()
        ]
        dashboard = v8.dashboard(
            state.battery_present,
            state.battery_percent,
            state.battery_charging,
        )
        themes = v8.themes.themes()
        theme_index = v8.themes.selected_index()
        active_theme = v8.themes.active()

        render_key = (
            view,
            tuple(queue),
            queue_source,
            queue_available,
            queue_status,
            v8.state.queue_index,
            tuple(
                (item.name, item.volume, item.muted)
                for item in mixer
            ),
            v8.state.mixer_index,
            tuple(notifications),
            dashboard.cpu_percent,
            dashboard.memory_percent,
            dashboard.battery_text,
            dashboard.network_text,
            theme_index,
            active_theme.get("name", ""),
            serial_manager.is_connected,
        )

        if (
            serial_manager.is_connected
            and render_key != last_render_key
        ):
            try:
                image = await asyncio.to_thread(
                    render_view,
                    view=view,
                    theme=active_theme,
                    queue=queue,
                    queue_index=v8.state.queue_index,
                    queue_source=queue_source,
                    queue_available=queue_available,
                    queue_status=queue_status,
                    mixer=mixer,
                    mixer_index=v8.state.mixer_index,
                    notifications=notifications,
                    dashboard=dashboard,
                    themes=themes,
                    theme_index=theme_index,
                )

                sent = await asyncio.to_thread(
                    serial_manager.send_view_image,
                    image,
                    VIEW_WIDTH,
                    VIEW_HEIGHT,
                )

                if sent:
                    last_render_key = render_key

            except Exception as exc:
                log(
                    "V8 view render failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        if view == "dashboard":
            await asyncio.sleep(2.0)
        elif view == "mixer":
            await asyncio.sleep(0.8)
        else:
            await asyncio.sleep(0.25)


async def main() -> None:
    reset_log()
    spotify = SpotifyController()
    volume = VolumeController()
    v8 = V8Controller()
    view_navigator = V8ViewNavigator.create(v8)
    serial_manager = SerialManager()
    state = AppState()
    queue_controller = QueueController(
        spotify,
        state,
        v8,
    )
    state.view_mode = view_navigator.current
    stop_event = asyncio.Event()

    await spotify.initialize()

    connection_task = asyncio.create_task(
        serial_manager.maintain_connection(stop_event)
    )

    try:
        await asyncio.gather(
            polling_loop(
                spotify,
                volume,
                serial_manager,
                state,
                stop_event,
                log=log,
                display_state=display_state,
            ),
            artwork_loop(
                spotify,
                serial_manager,
                state,
                stop_event,
                log=log,
            ),
            metadata_image_loop(
                serial_manager,
                state,
                stop_event,
                log=log,
            ),
            source_image_loop(
                serial_manager,
                state,
                stop_event,
                log=log,
            ),
            command_loop(
                spotify,
                volume,
                serial_manager,
                state,
                stop_event,
            ),
            serial_command_loop(
                spotify,
                volume,
                serial_manager,
                state,
                stop_event,
                v8,
                view_navigator,
                queue_controller,
            ),
            v8_view_loop(
                spotify,
                serial_manager,
                state,
                stop_event,
                v8,
                view_navigator,
                queue_controller,
            ),
        )
    finally:
        stop_event.set()
        connection_task.cancel()
        serial_manager.disconnect()

        try:
            await connection_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Stopped by keyboard interrupt.")
    except Exception as exc:
        log(f"Fatal error: {type(exc).__name__}: {exc}")