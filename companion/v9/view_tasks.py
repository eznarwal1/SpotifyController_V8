from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from serial_manager import SerialManager
from lyrics import LyricsClient
from spotify_controller import SpotifyController
from ui_state import AppState
from v8_controller import V8Controller
from v8_renderer import (
    HEIGHT as VIEW_HEIGHT,
)
from v8_renderer import (
    WIDTH as VIEW_WIDTH,
)
from v8_renderer import (
    render_view,
)
from v9.navigation_bridge import V8ViewNavigator
from v9.queue_controller import QueueController

LogFn = Callable[[str], None]


async def v8_view_loop(
    spotify: SpotifyController,
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    v8: V8Controller,
    view_navigator: V8ViewNavigator,
    queue_controller: QueueController,
    *,
    log: LogFn,
) -> None:
    last_render_key: tuple | None = None
    lyrics_client = LyricsClient()
    lyric_track_key: tuple[str, str, int] | None = None
    lyric_position = 0
    lyric_position_at = time.monotonic()
    lyric_was_playing = False

    while not stop_event.is_set():
        view = view_navigator.current
        state.view_mode = view

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

        if view == "queue":
            last_render_key = None
            await asyncio.sleep(0.25)
            continue

        state.brightness = v8.state.brightness

        lyric_lines: tuple[str, ...] = ()
        lyric_active_index = -1
        lyric_status = ""

        if view == "lyrics":
            media = state.media
            if not state.spotify_connected or not media.title:
                lyric_status = "No active track"
            else:
                current_track_key = (
                    media.title,
                    media.artist,
                    media.duration_seconds,
                )
                now = time.monotonic()
                if (
                    current_track_key != lyric_track_key
                    or media.position_seconds != lyric_position
                    or media.is_playing != lyric_was_playing
                ):
                    lyric_track_key = current_track_key
                    lyric_position = media.position_seconds
                    lyric_position_at = now
                    lyric_was_playing = media.is_playing

                projected_position = float(lyric_position)
                if media.is_playing:
                    projected_position += now - lyric_position_at

                lyrics = await asyncio.to_thread(
                    lyrics_client.get,
                    media.title,
                    media.artist,
                    media.album,
                    media.duration_seconds,
                )
                lyric_lines = tuple(line.text for line in lyrics.lines)
                lyric_active_index = lyrics.active_index(
                    projected_position
                )
                lyric_status = lyrics.status

        if view == "discord":
            server, channel, messages, discord_source = (
                spotify.get_discord_message_snapshot()
            )
            source_suffix = (
                "Desktop"
                if discord_source == "desktop"
                else "Web"
            )

            if server and channel:
                state.queue_source = (
                    f"{server} / #{channel} · {source_suffix}"
                )
            elif channel:
                state.queue_source = f"#{channel} · {source_suffix}"
            elif server:
                state.queue_source = f"{server} · {source_suffix}"
            else:
                state.queue_source = f"Discord · {source_suffix}"

            state.queue_entries = list(messages)[-6:]
            state.queue_selected_index = 0

            last_render_key = None
            await asyncio.sleep(0.25)
            continue

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
            v8.state.brightness,
            lyric_lines,
            lyric_active_index,
            lyric_status,
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
                    mixer=[],
                    mixer_index=0,
                    themes=themes,
                    theme_index=theme_index,
                    brightness=v8.state.brightness,
                    lyric_lines=lyric_lines,
                    lyric_active_index=lyric_active_index,
                    lyric_status=lyric_status,
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

        await asyncio.sleep(0.10 if view == "lyrics" else 0.25)
