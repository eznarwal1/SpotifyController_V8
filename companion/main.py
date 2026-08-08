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
from v9.command_router import process_display_command
from v9.navigation_bridge import V8ViewNavigator
from v9.queue_controller import QueueController
from v9.runtime_state import polling_loop, send_current_state
from v9.media_tasks import artwork_loop, metadata_image_loop, source_image_loop
from v9.input_tasks import command_loop, serial_command_loop
from v9.view_tasks import v8_view_loop
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
                send_current_state=send_current_state,
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
                send_current_state=send_current_state,
                log=log,
            ),
            v8_view_loop(
                spotify,
                serial_manager,
                state,
                stop_event,
                v8,
                view_navigator,
                queue_controller,
                log=log,
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