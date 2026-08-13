from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from background_renderer import (
    BACKGROUND_HEIGHT,
    BACKGROUND_WIDTH,
    render_and_cache_blurred_background,
)
from metadata_renderer import (
    PANEL_HEIGHT,
    PANEL_WIDTH,
    SOURCE_HEIGHT,
    SOURCE_WIDTH,
    MetadataPanel,
    render_metadata_panel,
    render_source_button,
    set_ui_background,
    ui_background_revision,
)
from serial_manager import SerialManager
from spotify_controller import SpotifyController
from ui_state import AppState

ARTWORK_WIDTH = 210
ARTWORK_HEIGHT = 210
ARTWORK_RETRY_SECONDS = 15.0
ARTWORK_METADATA_DELAY_SECONDS = 0.12
ARTWORK_LOOP_INTERVAL_SECONDS = 0.05

LogFn = Callable[[str], None]


@dataclass(slots=True)
class ArtworkTransferState:
    artwork_digest: str = ""
    background_digest: str = ""


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


async def prepare_and_send_artwork(
    track_key: tuple[str, str, str],
    spotify: SpotifyController,
    serial_manager: SerialManager,
    state: AppState,
    transfer_state: ArtworkTransferState,
    *,
    log: LogFn,
) -> bool:
    """
    Prepare the newest track's genuine artwork without disturbing the
    currently displayed image while lookup is in progress.
    """
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
            await asyncio.sleep(ARTWORK_METADATA_DELAY_SECONDS)

            if current_track_key(state) != track_key:
                log(
                    "Artwork lookup cancelled before network request because "
                    f"the track changed: {track_key!r}"
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
                "Artwork network preparation finished in "
                f"{lookup_elapsed:.3f}s for {track_key!r}"
            )

    except asyncio.CancelledError:
        log(f"Artwork worker cancelled for stale track {track_key!r}")
        raise
    except Exception as exc:
        log(
            "Artwork retrieval failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return False

    if artwork is None:
        log(
            "No genuine artwork found; preserving the currently displayed "
            f"artwork for {track_key!r}"
        )
        return False

    if current_track_key(state) != track_key:
        log(
            "Discarding stale artwork because the track changed: "
            f"{track_key!r}"
        )
        return False

    if not serial_manager.is_connected:
        return False

    artwork_digest = hashlib.sha256(artwork).hexdigest()

    if artwork_digest == transfer_state.artwork_digest:
        log(
            "Artwork is identical to the displayed album art; "
            f"skipping serial retransmission for {track_key!r}"
        )
        return True

    try:
        background_digest, background = await asyncio.to_thread(
            render_and_cache_blurred_background,
            artwork,
            ARTWORK_WIDTH,
            ARTWORK_HEIGHT,
        )

        if current_track_key(state) != track_key:
            log(
                "Artwork became stale before serial transfer; "
                f"discarding {track_key!r}"
            )
            return False

        send_started = loop.time()
        artwork_sent = await asyncio.to_thread(
            serial_manager.send_artwork,
            artwork,
            ARTWORK_WIDTH,
            ARTWORK_HEIGHT,
        )

        if not artwork_sent:
            return False

        transfer_state.artwork_digest = artwork_digest

        if current_track_key(state) != track_key:
            log(
                "Track changed during artwork transfer; suppressing stale "
                f"background for {track_key!r}"
            )
            return False

        if background_digest != transfer_state.background_digest:
            background_sent = await asyncio.to_thread(
                serial_manager.send_background_image,
                background,
                BACKGROUND_WIDTH,
                BACKGROUND_HEIGHT,
            )

            if background_sent:
                transfer_state.background_digest = background_digest
                await asyncio.to_thread(
                    set_ui_background,
                    background,
                    BACKGROUND_WIDTH,
                    BACKGROUND_HEIGHT,
                )
            else:
                log(
                    "Background packet was not sent; keeping the previous "
                    "metadata/source compositor background"
                )
        else:
            log("Blurred background unchanged; skipping retransmission.")

        send_elapsed = loop.time() - send_started
        log(
            "Artwork/background transaction completed in "
            f"{send_elapsed:.3f}s for {track_key!r}"
        )
        return True

    except asyncio.CancelledError:
        log(f"Artwork transfer cancelled for stale track {track_key!r}")
        raise
    except Exception as exc:
        log(
            "Artwork/background send failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return False


async def source_image_loop(
    serial_manager: SerialManager,
    state: AppState,
    stop_event: asyncio.Event,
    *,
    log: LogFn,
) -> None:
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
    *,
    log: LogFn,
) -> None:
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
    *,
    log: LogFn,
) -> None:
    last_sent_key: tuple[str, str, str] | None = None
    last_attempted_key: tuple[str, str, str] | None = None
    last_attempt_time = 0.0
    active_key: tuple[str, str, str] | None = None
    active_task: asyncio.Task[bool] | None = None
    was_connected = False
    transfer_state = ArtworkTransferState()

    log("Artwork stability loop started.")

    while not stop_event.is_set():
        connected = serial_manager.is_connected
        track_key = current_track_key(state)
        now = asyncio.get_running_loop().time()

        if (
            active_task is not None
            and not active_task.done()
            and active_key is not None
            and track_key != active_key
        ):
            log(
                "Cancelling stale artwork worker: "
                f"{active_key!r} -> {track_key!r}"
            )
            active_task.cancel()
            active_task = None
            active_key = None

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
            transfer_state.artwork_digest = ""
            transfer_state.background_digest = ""

            if active_task is not None:
                active_task.cancel()
                active_task = None
                active_key = None

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
                    transfer_state,
                    log=log,
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
