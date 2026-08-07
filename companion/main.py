from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import threading
from typing import Any

from protocol import make_state_message
from serial_manager import SerialManager
from spotify_controller import SpotifyController
from ui_state import AppState, MediaState
from volume_controller import VolumeController
from system_status import get_battery_status
from v8_controller import V8Controller
from v8_renderer import WIDTH as VIEW_WIDTH, HEIGHT as VIEW_HEIGHT, render_view
from v9.queue_protocol import build_queue_state
from v9.mixer_model import build_mixer_state
from background_renderer import (
    BACKGROUND_WIDTH,
    BACKGROUND_HEIGHT,
    render_blurred_background,
)
from metadata_renderer import (
    MetadataPanel,
    PANEL_WIDTH,
    PANEL_HEIGHT,
    SOURCE_WIDTH,
    SOURCE_HEIGHT,
    render_metadata_panel,
    render_source_button,
    set_ui_background,
    ui_background_revision,
)


ARTWORK_WIDTH = 210
ARTWORK_HEIGHT = 210
ARTWORK_RETRY_SECONDS = 2.0
ARTWORK_METADATA_DELAY_SECONDS = 0.02
ARTWORK_LOOP_INTERVAL_SECONDS = 0.05
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

    if serial_manager.is_connected:
        await asyncio.to_thread(
            serial_manager.send_line,
            make_state_message(state),
        )


def update_native_queue_window(
    spotify: SpotifyController,
    state: AppState,
    v8: V8Controller,
) -> tuple[list[str], int]:
    # Keep the complete Queue index on the PC while sending only four rows.
    queue = spotify._chrome_bridge.selected_or_playing_queue()

    (
        queue_source,
        _queue_available,
        _queue_status,
    ) = spotify._chrome_bridge.selected_queue_status()

    total = len(queue)

    if total == 0:
        v8.state.queue_index = 0
        state.queue_source = queue_source
        state.queue_entries = []
        state.queue_selected_index = 0
        return queue, 0

    selected = max(0, min(v8.state.queue_index, total - 1))
    v8.state.queue_index = selected

    start = max(
        0,
        min(
            selected - 1,
            max(0, total - 4),
        ),
    )

    state.queue_entries = queue[start:start + 4]
    state.queue_selected_index = selected - start
    state.queue_source = (
        f"{queue_source}  {selected + 1}/{total}"
        if queue_source
        else f"{selected + 1}/{total}"
    )

    return queue, selected


async def process_display_command(
    message: dict[str, Any] | None,
    spotify: SpotifyController,
    volume: VolumeController,
    state: AppState,
    serial_manager: SerialManager,
    v8: V8Controller,
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
            update_native_queue_window(spotify, state, v8)

            if serial_manager.is_connected:
                await asyncio.to_thread(
                    serial_manager.send_line,
                    make_state_message(state),
                )

            log("Queue selection returned to beginning.")
        return

    if command in ("utility_previous", "utility_next"):
        if v8.state.view == "queue":
            queue = spotify._chrome_bridge.selected_or_playing_queue()

            if queue:
                direction = -1 if command == "utility_previous" else 1
                v8.state.queue_index = max(
                    0,
                    min(
                        v8.state.queue_index + direction,
                        len(queue) - 1,
                    ),
                )
                update_native_queue_window(spotify, state, v8)

                if serial_manager.is_connected:
                    await asyncio.to_thread(
                        serial_manager.send_line,
                        make_state_message(state),
                    )
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
                    v8.state.queue_index = max(
                        0,
                        min(
                            v8.state.queue_index + direction,
                            len(queue) - 1,
                        ),
                    )
                    update_native_queue_window(spotify, state, v8)

                    if serial_manager.is_connected:
                        await asyncio.to_thread(
                            serial_manager.send_line,
                            make_state_message(state),
                        )
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


async def polling_loop(
    spotify: SpotifyController,
    volume: VolumeController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
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

            # Metadata is sent independently of artwork retrieval.
            # A slow network lookup can no longer delay title/artist/progress.
            if serial_manager.is_connected:
                await asyncio.to_thread(
                    serial_manager.send_line,
                    make_state_message(state),
                )

            display_state(state)

        except Exception as exc:
            log(f"Polling loop error: {type(exc).__name__}: {exc}")

        await asyncio.sleep(1.0)


def current_track_key(
    state: AppState,
) -> tuple[str, str, str] | None:
    if not state.spotify_connected:
        return None

    title = state.media.title.strip()
    artist = state.media.artist.strip()
    album = state.media.album.strip()

    if not title and not artist:
        return None

    return title, artist, album


async def prepare_and_send_artwork(
    track_key: tuple[str, str, str],
    spotify: SpotifyController,
    serial_manager: SerialManager,
    state: AppState,
) -> bool:
    """Prepare and send one track's artwork without blocking metadata polling."""
    loop = asyncio.get_running_loop()

    try:
        cache_started = loop.time()
        artwork = await spotify.get_cached_album_art_rgb565_for_track(
            track_key[0],
            track_key[1],
            track_key[2],
            ARTWORK_WIDTH,
            ARTWORK_HEIGHT,
        )
        cache_elapsed = loop.time() - cache_started

        if artwork is not None:
            log(
                f"Artwork cache ready in {cache_elapsed:.3f}s for "
                f"{track_key!r}"
            )
        else:
            # Briefly allow Spotify's title/album metadata to settle after a skip.
            await asyncio.sleep(ARTWORK_METADATA_DELAY_SECONDS)

            if current_track_key(state) != track_key:
                log(
                    "Skipped network artwork lookup because track changed: "
                    f"{track_key!r}"
                )
                return False

            lookup_started = loop.time()
            artwork = await spotify.get_album_art_rgb565_for_track(
                track_key[0],
                track_key[1],
                track_key[2],
                ARTWORK_WIDTH,
                ARTWORK_HEIGHT,
            )
            lookup_elapsed = loop.time() - lookup_started
            log(
                f"Artwork network preparation finished in "
                f"{lookup_elapsed:.3f}s for {track_key!r}"
            )

    except Exception as exc:
        log(
            "Artwork retrieval failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return False

    if artwork is None:
        return False

    if current_track_key(state) != track_key:
        log(
            "Discarding stale artwork because the track changed: "
            f"{track_key!r}"
        )
        return False

    if not serial_manager.is_connected:
        return False

    try:
        send_started = loop.time()
        sent = await asyncio.to_thread(
            serial_manager.send_artwork,
            artwork,
            ARTWORK_WIDTH,
            ARTWORK_HEIGHT,
        )

        if sent:
            try:
                background = await asyncio.to_thread(
                    render_blurred_background,
                    artwork,
                    ARTWORK_WIDTH,
                    ARTWORK_HEIGHT,
                )
                background_sent = await asyncio.to_thread(
                    serial_manager.send_background_image,
                    background,
                    BACKGROUND_WIDTH,
                    BACKGROUND_HEIGHT,
                )

                if background_sent:
                    await asyncio.to_thread(
                        set_ui_background,
                        background,
                        BACKGROUND_WIDTH,
                        BACKGROUND_HEIGHT,
                    )
                else:
                    log(
                        "Background packet was not sent; keeping the "
                        "existing metadata/source background to avoid seams"
                    )

                log(
                    "Blurred artwork background send returned "
                    f"{background_sent}"
                )
            except Exception as exc:
                log(
                    "Blurred background preparation failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        send_elapsed = loop.time() - send_started
        log(
            f"Artwork serial send returned {sent} "
            f"in {send_elapsed:.3f}s"
        )
        return sent
    except Exception as exc:
        log(
            f"Artwork send failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return False


def current_metadata_key(
    state: AppState,
) -> tuple[str, str, str, str] | None:
    if not state.spotify_connected:
        return None

    return (
        state.media.title.strip(),
        state.media.artist.strip(),
        state.media.album.strip(),
        state.media.application.strip(),
    )


async def source_image_loop(
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
) -> None:
    """Render the source selector label on Windows and send it as pixels."""
    last_source_key: tuple[str, int] | None = None
    was_connected = False

    while not stop_event.is_set():
        connected = serial_manager.is_connected

        if state.spotify_connected:
            source = state.media.application.strip() or "Auto"
        else:
            source = "Auto"

        source_key = (
            source,
            ui_background_revision(),
        )

        if connected and (
            not was_connected or source_key != last_source_key
        ):
            try:
                rgb565 = await asyncio.to_thread(
                    render_source_button,
                    source,
                )
                sent = await asyncio.to_thread(
                    serial_manager.send_source_image,
                    rgb565,
                    SOURCE_WIDTH,
                    SOURCE_HEIGHT,
                )

                if sent:
                    last_source_key = source_key
                    log(f"Source image sent for {source!r}")
            except Exception as exc:
                log(
                    "Source image failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        if not connected:
            last_source_key = None

        was_connected = connected
        await asyncio.sleep(0.10)


async def metadata_image_loop(
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
) -> None:
    """Render multilingual metadata on Windows and send it as RGB565 pixels."""
    last_key: tuple[str, str, str, str, int] | None = None
    was_connected = False

    while not stop_event.is_set():
        connected = serial_manager.is_connected
        metadata = current_metadata_key(state)
        key = (
            None
            if metadata is None
            else (
                metadata[0],
                metadata[1],
                metadata[2],
                metadata[3],
                ui_background_revision(),
            )
        )

        if connected and key is not None and (
            not was_connected or key != last_key
        ):
            panel = MetadataPanel(
                title=key[0],
                artist=key[1],
                album=key[2],
                source=key[3],
            )

            try:
                rgb565 = await asyncio.to_thread(
                    render_metadata_panel,
                    panel,
                )
                sent = await asyncio.to_thread(
                    serial_manager.send_metadata_image,
                    rgb565,
                    PANEL_WIDTH,
                    PANEL_HEIGHT,
                )
                if sent:
                    last_key = key
                    log(f"Metadata image sent for {key!r}")
            except Exception as exc:
                log(
                    "Metadata image failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        if not connected:
            last_key = None

        was_connected = connected
        await asyncio.sleep(0.10)


async def artwork_loop(
    spotify: SpotifyController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
) -> None:
    """
    Run artwork retrieval as a latest-track background job.

    Cache hits are sent immediately. Cache misses use the network in this
    separate task, so title, artist, album, and progress keep updating.
    """
    last_sent_key: tuple[str, str, str] | None = None
    last_attempted_key: tuple[str, str, str] | None = None
    last_attempt_time = 0.0
    active_key: tuple[str, str, str] | None = None
    active_task: asyncio.Task[bool] | None = None
    was_connected = False

    log("V6 universal artwork loop started.")

    while not stop_event.is_set():
        connected = serial_manager.is_connected
        track_key = current_track_key(state)
        now = asyncio.get_running_loop().time()

        if active_task is not None and active_task.done():
            try:
                sent = active_task.result()
            except asyncio.CancelledError:
                sent = False
            except Exception as exc:
                log(
                    "Unexpected artwork worker failure: "
                    f"{type(exc).__name__}: {exc}"
                )
                sent = False

            if sent and active_key is not None:
                last_sent_key = active_key

            active_task = None
            active_key = None

        if not connected:
            was_connected = False
            last_sent_key = None
            await asyncio.sleep(0.20)
            continue

        connection_changed = connected and not was_connected

        retry_allowed = (
            track_key != last_attempted_key
            or now - last_attempt_time >= ARTWORK_RETRY_SECONDS
        )

        needs_artwork = (
            track_key is not None
            and (connection_changed or track_key != last_sent_key)
            and retry_allowed
        )

        # Start only one network worker at a time. If the track changes while
        # it runs, the worker discards stale data, and the next loop starts the
        # newest track immediately afterward.
        if needs_artwork and active_task is None:
            last_attempted_key = track_key
            last_attempt_time = now
            active_key = track_key
            active_task = asyncio.create_task(
                prepare_and_send_artwork(
                    track_key,
                    spotify,
                    serial_manager,
                    state,
                )
            )

        was_connected = connected
        await asyncio.sleep(ARTWORK_LOOP_INTERVAL_SECONDS)

    if active_task is not None:
        active_task.cancel()
        try:
            await active_task
        except asyncio.CancelledError:
            pass


async def serial_command_loop(
    spotify: SpotifyController,
    volume: VolumeController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    v8: V8Controller,
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
) -> None:
    last_render_key: tuple | None = None

    while not stop_event.is_set():
        view = v8.state.view
        state.view_mode = view
        state.notification_text = v8.notifications.latest_text()

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

        queue, _queue_selected = update_native_queue_window(
            spotify,
            state,
            v8,
        )
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
    serial_manager = SerialManager()
    state = AppState()
    state.view_mode = v8.state.view
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
            ),
            artwork_loop(
                spotify,
                serial_manager,
                state,
                stop_event,
            ),
            metadata_image_loop(
                serial_manager,
                state,
                stop_event,
            ),
            source_image_loop(
                serial_manager,
                state,
                stop_event,
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
            ),
            v8_view_loop(
                spotify,
                serial_manager,
                state,
                stop_event,
                v8,
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