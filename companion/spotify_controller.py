from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import struct
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont, ImageOps
from winrt.windows.media import MediaPlaybackAutoRepeatMode
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSession,
    GlobalSystemMediaTransportControlsSessionManager,
)

from chrome_bridge import ChromeTab, get_chrome_bridge
from discord_desktop import get_discord_desktop_bridge
from ui_state import MediaState

USER_AGENT = "SpotifyControllerDisplay/4.0 (personal desktop display)"
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "artwork_cache"
LOOKUP_LOG_PATH = BASE_DIR / "artwork_lookup.log"
MEMORY_CACHE_LIMIT = 50

# V4 shares one cached image across tracks from the same artist/album.
# This prevents a new MusicBrainz lookup for every song on the same album.
CACHE_SCHEMA_VERSION = "v5-real-art-only"


def _log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)

    try:
        with LOOKUP_LOG_PATH.open("a", encoding="utf-8", buffering=1) as file:
            file.write(line + "\n")
    except OSError as exc:
        logging.debug("_log: failed to write lookup log: %s", exc)


def _seconds(value) -> int:
    if value is None:
        return 0
    if hasattr(value, "total_seconds"):
        return max(0, int(value.total_seconds()))
    return 0


def _repeat_mode_name(value: Any) -> str | None:
    """Normalize WinRT repeat values to None, List, or Track."""
    if value is None:
        return None

    try:
        if value == MediaPlaybackAutoRepeatMode.NONE:
            return "None"
        if value == MediaPlaybackAutoRepeatMode.LIST:
            return "List"
        if value == MediaPlaybackAutoRepeatMode.TRACK:
            return "Track"
    except Exception as exc:
        logging.debug("_repeat_mode_name: MediaPlaybackAutoRepeatMode check failed: %s", exc)

    name = getattr(value, "name", None)
    text_value = str(name if name is not None else value).strip().casefold()

    if "track" in text_value:
        return "Track"
    if "list" in text_value or "all" in text_value:
        return "List"
    if "none" in text_value or "off" in text_value:
        return "None"

    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = None

    if numeric == 0:
        return "None"
    if numeric == 1:
        return "List"
    if numeric == 2:
        return "Track"

    return None


def _playback_status_name(value: Any) -> str:
    return str(getattr(value, "name", value)).strip().title()


def _friendly_application_name(app_id: str) -> str:
    lowered = app_id.casefold()

    mappings = (
        ("spotify", "Spotify"),
        ("chrome", "Chrome"),
        ("msedge", "Microsoft Edge"),
        ("firefox", "Firefox"),
        ("vlc", "VLC"),
        ("applemusic", "Apple Music"),
        ("itunes", "iTunes"),
        ("wmplayer", "Windows Media Player"),
        ("zune", "Media Player"),
        ("amazonmusic", "Amazon Music"),
    )

    for token, friendly in mappings:
        if token in lowered:
            return friendly

    leaf = re.split(r"[!\\/]", app_id)[-1]
    leaf = re.sub(r"\.exe$", "", leaf, flags=re.IGNORECASE)
    return leaf or "Media"


def _clean_search_text(value: str) -> str:
    value = value.replace("\ufffd", " ")
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[\u2022\u00b7\u2010-\u2015_/]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _normalized(value: str) -> str:
    value = _clean_search_text(value).casefold()
    value = re.sub(
        r"\([^)]*(deluxe|remaster|edition|version)[^)]*\)",
        " ",
        value,
    )
    value = re.sub(
        r"\[[^]]*(deluxe|remaster|edition|version)[^]]*\]",
        " ",
        value,
    )
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _similarity(left: str, right: str) -> float:
    left_normalized = _normalized(left)
    right_normalized = _normalized(right)

    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def _artist_credit_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""

    pieces: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            pieces.append(name)
        joinphrase = item.get("joinphrase")
        if isinstance(joinphrase, str):
            pieces.append(joinphrase)
    return "".join(pieces).strip()


def _request_json(request: Request, timeout: float = 12.0) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _download_bytes(url: str, timeout: float = 15.0) -> bytes | None:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        if exc.code in (404, 410):
            return None
        raise RuntimeError(f"Artwork download HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Artwork download error: {exc.reason}") from exc


class SpotifyController:
    def __init__(self) -> None:
        self.manager: GlobalSystemMediaTransportControlsSessionManager | None = None
        self._repeat_mode = "None"
        self._selected_session: GlobalSystemMediaTransportControlsSession | None = None
        self._manual_session_key: tuple[str, str] | None = None
        self._manual_chrome_tab_id: int | None = None
        self._chrome_bridge = get_chrome_bridge()
        self._discord_desktop = get_discord_desktop_bridge()
        self._current_application_name = "Media"
        self._artwork_cache: dict[tuple[str, str, str, int, int], bytes] = {}
        self._last_musicbrainz_request = 0.0
        self._musicbrainz_lock = threading.Lock()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        self.manager = (
            await GlobalSystemMediaTransportControlsSessionManager.request_async()
        )
        self._chrome_bridge.start()
        self._discord_desktop.start()
        _log("Chrome tab bridge listening on http://127.0.0.1:8765")
        _log("Discord Desktop UI Automation bridge started")

    def _all_sessions(
        self,
    ) -> list[GlobalSystemMediaTransportControlsSession]:
        if self.manager is None:
            raise RuntimeError("Media controller has not been initialized.")
        return list(self.manager.get_sessions())

    @staticmethod
    def _session_is_playing(
        session: GlobalSystemMediaTransportControlsSession,
    ) -> bool:
        try:
            status = session.get_playback_info().playback_status
            return _playback_status_name(status).casefold() == "playing"
        except Exception as exc:
            logging.debug("_session_is_playing: failed to get playback status: %s", exc)
            return False

    @staticmethod
    def _session_id(
        session: GlobalSystemMediaTransportControlsSession,
    ) -> str:
        return session.source_app_user_model_id or ""

    async def _session_key(
        self,
        session: GlobalSystemMediaTransportControlsSession,
    ) -> tuple[str, str]:
        """
        Identify an exposed Windows media session by application and title.

        This allows separate browser sessions to appear independently when
        Chrome or Edge publishes more than one GSMTC session.
        """
        app_id = self._session_id(session)

        try:
            properties = await session.try_get_media_properties_async()
            title = (properties.title or "").strip()
        except Exception as exc:
            logging.debug("_session_key: try_get_media_properties_async failed: %s", exc)
            title = ""

        return app_id, title

    async def _session_display_name(
        self,
        session: GlobalSystemMediaTransportControlsSession,
    ) -> str:
        app_id, title = await self._session_key(session)
        application = _friendly_application_name(app_id)

        if title:
            return f"{application} — {title}"
        return application

    async def available_media_sources(self) -> list[str]:
        """Return every media session currently exposed by Windows."""
        names: list[str] = []

        for session in self._all_sessions():
            names.append(await self._session_display_name(session))

        return names

    async def cycle_media_source(self) -> str:
        """
        Cycle through Auto, individual Chrome media tabs, and Windows media
        sessions.

        Chrome tabs are listed independently when the companion extension is
        installed and connected.
        """
        chrome_tabs = self._chrome_bridge.list_tabs()
        sessions = self._all_sessions()

        # When per-tab Chrome data is available, hide the browser's combined
        # GSMTC session to avoid showing the same browser twice.
        if chrome_tabs:
            sessions = [
                session
                for session in sessions
                if not any(
                    token in self._session_id(session).casefold()
                    for token in ("chrome", "msedge")
                )
            ]

        entries: list[tuple[str, object, str]] = []

        for tab in chrome_tabs:
            entries.append(("chrome", tab.tab_id, tab.source_label))

        for session in sessions:
            key = await self._session_key(session)
            name = await self._session_display_name(session)
            entries.append(("gsmtc", key, name))

        if not entries:
            self.use_automatic_source_selection()
            return "Auto"

        current_index = -1

        if self._manual_chrome_tab_id is not None:
            for index, entry in enumerate(entries):
                if entry[0] == "chrome" and entry[1] == self._manual_chrome_tab_id:
                    current_index = index
                    break
        elif self._manual_session_key is not None:
            for index, entry in enumerate(entries):
                if entry[0] == "gsmtc" and entry[1] == self._manual_session_key:
                    current_index = index
                    break

        # A short press cycles actual sources continuously. Auto selection is
        # deliberately reserved for the source button's long-press command.
        next_index = (current_index + 1) % len(entries)

        kind, identifier, display_name = entries[next_index]

        if kind == "chrome":
            self._manual_chrome_tab_id = int(identifier)
            self._manual_session_key = None
            self._selected_session = None
            _log(f"Chrome tab manually selected: {display_name}")
        else:
            self._manual_session_key = identifier  # type: ignore[assignment]
            self._manual_chrome_tab_id = None

            for session in sessions:
                if await self._session_key(session) == self._manual_session_key:
                    self._selected_session = session
                    break

            _log(f"Media session manually selected: {display_name}")

        return display_name

    def use_automatic_source_selection(self) -> None:
        """Return to automatic active-source selection."""
        self._manual_session_key = None
        self._manual_chrome_tab_id = None
        _log("Media source selection changed to Auto")

    def _selected_chrome_tab(self) -> ChromeTab | None:
        if self._manual_chrome_tab_id is None:
            return None

        tab = self._chrome_bridge.get_tab(self._manual_chrome_tab_id)

        if tab is None:
            _log(
                "The selected Chrome tab is no longer available; "
                "returning to Auto"
            )
            self._manual_chrome_tab_id = None

        return tab

    async def _select_active_media_session(
        self,
    ) -> GlobalSystemMediaTransportControlsSession | None:
        sessions = self._all_sessions()

        if not sessions:
            self._selected_session = None
            return None

        if self._manual_session_key is not None:
            # A session's title is part of its display/cycle key, but titles
            # are mutable metadata rather than session identity. Keep the
            # exact object selected while Windows still exposes it, and
            # refresh its key when Spotify changes tracks or playback state.
            if self._selected_session in sessions:
                selected_app_id = self._session_id(self._selected_session)

                if selected_app_id == self._manual_session_key[0]:
                    self._manual_session_key = await self._session_key(
                        self._selected_session
                    )
                    return self._selected_session

            for session in sessions:
                if await self._session_key(session) == self._manual_session_key:
                    self._selected_session = session
                    return session

            _log(
                "The manually selected media session is no longer available; "
                "returning to Auto"
            )
            self._manual_session_key = None

        playing_sessions = [
            session
            for session in sessions
            if self._session_is_playing(session)
        ]

        if playing_sessions:
            try:
                current = self.manager.get_current_session()
            except Exception as exc:
                logging.debug("_select_active_media_session: get_current_session failed: %s", exc)
                current = None

            if current is not None and current in playing_sessions:
                selected = current
            elif self._selected_session in playing_sessions:
                selected = self._selected_session
            else:
                selected = playing_sessions[0]
        elif self._selected_session in sessions:
            selected = self._selected_session
        else:
            try:
                selected = self.manager.get_current_session()
            except Exception as exc:
                logging.debug("_select_active_media_session: fallback get_current_session failed: %s", exc)
                selected = None

            if selected is None:
                spotify_sessions = [
                    session
                    for session in sessions
                    if "spotify" in session.source_app_user_model_id.casefold()
                ]
                selected = spotify_sessions[0] if spotify_sessions else sessions[0]

        self._selected_session = selected
        return selected

    async def _find_spotify_session(
        self,
    ) -> GlobalSystemMediaTransportControlsSession | None:
        """Compatibility alias retained for existing artwork methods."""
        return await self._select_active_media_session()

    async def toggle_play_pause(self) -> bool:
        chrome_tab = self._selected_chrome_tab()
        if chrome_tab is not None:
            return self._chrome_bridge.enqueue_command(
                chrome_tab.tab_id,
                "play_pause",
            )

        session = await self._select_active_media_session()
        return (
            False
            if session is None
            else await session.try_toggle_play_pause_async()
        )

    async def previous_track(self) -> bool:
        chrome_tab = self._selected_chrome_tab()
        if chrome_tab is not None:
            return self._chrome_bridge.enqueue_command(
                chrome_tab.tab_id,
                "previous",
            )

        session = await self._select_active_media_session()
        return (
            False
            if session is None
            else await session.try_skip_previous_async()
        )

    async def next_track(self) -> bool:
        chrome_tab = self._selected_chrome_tab()
        if chrome_tab is not None:
            return self._chrome_bridge.enqueue_command(
                chrome_tab.tab_id,
                "next",
            )

        session = await self._select_active_media_session()
        return (
            False
            if session is None
            else await session.try_skip_next_async()
        )

    async def toggle_shuffle(self) -> bool:
        chrome_tab = self._selected_chrome_tab()
        if chrome_tab is not None:
            return self._chrome_bridge.enqueue_command(
                chrome_tab.tab_id,
                "shuffle_toggle",
            )

        session = await self._select_active_media_session()
        if session is None:
            return False

        playback_info = session.get_playback_info()
        current_value = getattr(
            playback_info,
            "is_shuffle_active",
            False,
        )
        current = bool(
            False if current_value is None else current_value
        )

        success = await session.try_change_shuffle_active_async(
            not current
        )

        if success:
            _log(
                "Shuffle changed to "
                f"{'On' if not current else 'Off'}"
            )
        else:
            _log("Shuffle change was rejected by the media session.")

        return success

    async def cycle_repeat_mode(self) -> bool:
        chrome_tab = self._selected_chrome_tab()
        if chrome_tab is not None:
            return self._chrome_bridge.enqueue_command(
                chrome_tab.tab_id,
                "repeat_cycle",
            )

        session = await self._select_active_media_session()
        if session is None:
            return False

        playback_info = session.get_playback_info()
        raw_repeat = getattr(playback_info, "auto_repeat_mode", None)
        reported_mode = _repeat_mode_name(raw_repeat)
        current_mode = reported_mode or self._repeat_mode

        if current_mode == "None":
            next_mode = MediaPlaybackAutoRepeatMode.LIST
            next_name = "List"
        elif current_mode == "List":
            next_mode = MediaPlaybackAutoRepeatMode.TRACK
            next_name = "Track"
        else:
            next_mode = MediaPlaybackAutoRepeatMode.NONE
            next_name = "None"

        success = await session.try_change_auto_repeat_mode_async(next_mode)

        if success:
            self._repeat_mode = next_name
            _log(f"Repeat changed to {next_name}")
        else:
            _log(
                "Repeat change was rejected by the Spotify media session: "
                f"{current_mode} -> {next_name}"
            )

        return success

    def get_discord_status(self) -> tuple[bool, bool, bool]:
        desktop = self._discord_desktop.snapshot()

        if desktop.accessibility_ready:
            return (
                desktop.voice_connected,
                desktop.muted,
                desktop.deafened,
            )

        return self._chrome_bridge.discord_status()

    def get_discord_message_snapshot(
        self,
    ) -> tuple[str, str, list[str], str]:
        desktop = self._discord_desktop.snapshot()

        if desktop.accessibility_ready:
            return (
                desktop.server,
                desktop.channel,
                list(desktop.messages),
                "desktop",
            )

        server, channel, messages = (
            self._chrome_bridge.discord_message_snapshot()
        )
        return server, channel, messages, "web"

    def toggle_discord_mute(self) -> bool:
        desktop = self._discord_desktop.snapshot()

        if desktop.accessibility_ready:
            return self._discord_desktop.enqueue_command("discord_mute")

        return self._chrome_bridge.enqueue_discord_command("discord_mute")

    def toggle_discord_deafen(self) -> bool:
        desktop = self._discord_desktop.snapshot()

        if desktop.accessibility_ready:
            return self._discord_desktop.enqueue_command("discord_deafen")

        return self._chrome_bridge.enqueue_discord_command("discord_deafen")

    async def get_state(self) -> MediaState | None:
        chrome_tab = self._selected_chrome_tab()

        if chrome_tab is not None:
            self._current_application_name = "Chrome"

            return MediaState(
                application=chrome_tab.source_label,
                title=chrome_tab.display_title,
                artist=chrome_tab.display_artist,
                album=chrome_tab.display_album,
                playback_status=(
                    "Playing" if chrome_tab.playing else "Paused"
                ),
                position_seconds=chrome_tab.position_seconds,
                duration_seconds=chrome_tab.duration_seconds,
                shuffle_active=chrome_tab.spotify_shuffle_active,
                repeat_mode=chrome_tab.spotify_repeat_mode,
            )

        session = await self._select_active_media_session()
        if session is None:
            return None

        media_properties = await session.try_get_media_properties_async()
        playback_info = session.get_playback_info()
        timeline = session.get_timeline_properties()
        status = playback_info.playback_status

        raw_repeat = getattr(playback_info, "auto_repeat_mode", None)
        reported_repeat = _repeat_mode_name(raw_repeat)

        if reported_repeat is not None:
            self._repeat_mode = reported_repeat

        shuffle_value = getattr(
            playback_info,
            "is_shuffle_active",
            False,
        )
        shuffle_active = bool(
            False if shuffle_value is None else shuffle_value
        )

        application_id = session.source_app_user_model_id or ""
        application_name = _friendly_application_name(application_id)
        self._current_application_name = application_name

        title = media_properties.title or "Unknown title"
        artist = media_properties.artist or application_name
        album = media_properties.album_title or application_name
        source_name = (
            f"{application_name} — {title}"
            if title and title != "Unknown title"
            else application_name
        )

        return MediaState(
            application=source_name,
            title=title,
            artist=artist,
            album=album,
            playback_status=_playback_status_name(status),
            position_seconds=_seconds(timeline.position),
            duration_seconds=_seconds(timeline.end_time),
            shuffle_active=shuffle_active,
            repeat_mode=self._repeat_mode,
        )

    def _musicbrainz_query_sync(self, query: str) -> dict[str, Any]:
        # MusicBrainz asks clients to stay at approximately one request/second.
        # The lock also prevents two artwork workers from racing this limiter.
        with self._musicbrainz_lock:
            elapsed = time.monotonic() - self._last_musicbrainz_request
            if elapsed < 1.05:
                time.sleep(1.05 - elapsed)

            url = (
                "https://musicbrainz.org/ws/2/recording/"
                f"?query={quote(query)}&fmt=json&limit=25"
            )
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
                method="GET",
            )
            result = _request_json(request)
            self._last_musicbrainz_request = time.monotonic()
            return result

    def _rank_musicbrainz_candidates_sync(
        self,
        title: str,
        artist: str,
        album: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        clean_title = _clean_search_text(title)
        clean_artist = _clean_search_text(artist)
        clean_album = _clean_search_text(album)

        queries: list[str] = []
        if clean_album:
            queries.append(
                f'recording:"{clean_title}" AND artist:"{clean_artist}" '
                f'AND release:"{clean_album}"'
            )
        queries.append(
            f'recording:"{clean_title}" AND artist:"{clean_artist}"'
        )

        release_candidates: dict[str, dict[str, Any]] = {}
        group_candidates: dict[str, dict[str, Any]] = {}

        for query_index, query in enumerate(queries):
            result = self._musicbrainz_query_sync(query)

            for recording in result.get("recordings", []):
                if not isinstance(recording, dict):
                    continue

                recording_title = str(recording.get("title") or "")
                recording_artist = _artist_credit_text(
                    recording.get("artist-credit")
                )
                mb_score = float(recording.get("score") or 0)

                title_similarity = _similarity(title, recording_title)
                artist_similarity = _similarity(artist, recording_artist)

                if title_similarity < 0.55 or artist_similarity < 0.45:
                    continue

                for release in recording.get("releases", []):
                    if not isinstance(release, dict):
                        continue

                    release_id = release.get("id")
                    release_title = str(release.get("title") or "")
                    release_artist = _artist_credit_text(
                        release.get("artist-credit")
                    )
                    album_similarity = (
                        _similarity(album, release_title)
                        if clean_album
                        else 0.5
                    )
                    release_artist_similarity = (
                        _similarity(artist, release_artist)
                        if release_artist
                        else artist_similarity
                    )

                    score = (
                        mb_score * 0.20
                        + title_similarity * 25.0
                        + artist_similarity * 25.0
                        + release_artist_similarity * 10.0
                        + album_similarity * 55.0
                    )

                    if query_index == 0 and clean_album:
                        score += 12.0
                    if (
                        str(release.get("status") or "").casefold()
                        == "official"
                    ):
                        score += 4.0

                    group = release.get("release-group", {})
                    group_id = (
                        group.get("id")
                        if isinstance(group, dict)
                        else None
                    )
                    group_title = (
                        str(group.get("title") or "")
                        if isinstance(group, dict)
                        else ""
                    )
                    primary_type = (
                        str(group.get("primary-type") or "")
                        if isinstance(group, dict)
                        else ""
                    )

                    if primary_type.casefold() in {"album", "single", "ep"}:
                        score += 2.0

                    candidate = {
                        "score": score,
                        "release_id": release_id,
                        "release_title": release_title,
                        "group_id": group_id,
                        "group_title": group_title,
                        "album_similarity": album_similarity,
                    }

                    if isinstance(release_id, str):
                        previous = release_candidates.get(release_id)
                        if (
                            previous is None
                            or score > float(previous["score"])
                        ):
                            release_candidates[release_id] = candidate

                    if isinstance(group_id, str):
                        group_album_similarity = (
                            _similarity(album, group_title)
                            if clean_album
                            else album_similarity
                        )
                        group_score = (
                            score + group_album_similarity * 10.0
                        )
                        group_candidate = {
                            **candidate,
                            "score": group_score,
                            "album_similarity": group_album_similarity,
                        }
                        previous = group_candidates.get(group_id)
                        if (
                            previous is None
                            or group_score > float(previous["score"])
                        ):
                            group_candidates[group_id] = group_candidate

            if (
                query_index == 0
                and clean_album
                and release_candidates
                and max(
                    float(candidate["album_similarity"])
                    for candidate in release_candidates.values()
                )
                >= 0.90
            ):
                break

        releases = sorted(
            release_candidates.values(),
            key=lambda candidate: float(candidate["score"]),
            reverse=True,
        )
        groups = sorted(
            group_candidates.values(),
            key=lambda candidate: float(candidate["score"]),
            reverse=True,
        )

        if releases:
            best = releases[0]
            _log(
                "Best MusicBrainz release: "
                f"{best['release_title']!r}, "
                f"album similarity={best['album_similarity']:.2f}, "
                f"score={best['score']:.1f}"
            )
        else:
            _log(
                f"No ranked MusicBrainz release for "
                f"{title!r} / {artist!r} / {album!r}"
            )

        return releases, groups

    @staticmethod
    def _make_placeholder_bytes_sync(
        application: str,
        title: str,
        width: int = 500,
        height: int = 500,
    ) -> bytes:
        image = Image.new("RGB", (width, height), (40, 40, 40))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        source = (application or "Media")[:28]
        caption = (title or "No artwork")[:48]

        draw.rectangle(
            (0, 0, width - 1, height - 1),
            outline=(90, 90, 90),
            width=3,
        )
        draw.text(
            (24, height // 2 - 26),
            source,
            fill=(255, 255, 255),
            font=font,
        )
        draw.text(
            (24, height // 2 + 4),
            caption,
            fill=(180, 180, 180),
            font=font,
        )

        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def _find_cover_bytes_sync(
        self,
        title: str,
        artist: str,
        album: str,
    ) -> bytes | None:
        releases, groups = self._rank_musicbrainz_candidates_sync(
            title,
            artist,
            album,
        )

        strong_releases = [
            candidate
            for candidate in releases
            if float(candidate["album_similarity"]) >= 0.82
        ]

        for candidate in strong_releases[:8]:
            release_id = candidate["release_id"]
            for size in ("500", "250"):
                raw = _download_bytes(
                    "https://coverartarchive.org/release/"
                    f"{release_id}/front-{size}"
                )
                if raw:
                    _log(
                        "Cover selected from release "
                        f"{candidate['release_title']!r} ({release_id})"
                    )
                    return raw

        for candidate in groups[:6]:
            group_id = candidate["group_id"]
            for size in ("500", "250"):
                raw = _download_bytes(
                    "https://coverartarchive.org/release-group/"
                    f"{group_id}/front-{size}"
                )
                if raw:
                    _log(
                        "Cover selected from release group "
                        f"{candidate['group_title']!r} ({group_id})"
                    )
                    return raw

        for candidate in releases[:5]:
            release_id = candidate["release_id"]
            for size in ("500", "250"):
                raw = _download_bytes(
                    "https://coverartarchive.org/release/"
                    f"{release_id}/front-{size}"
                )
                if raw:
                    _log(
                        "Fallback cover selected from release "
                        f"{candidate['release_title']!r} ({release_id})"
                    )
                    return raw

        _log(
            f"No Cover Art Archive image for "
            f"{title!r} / {artist!r} / {album!r}"
        )
        # Keep the artwork already displayed when no genuine cover exists.
        # Returning None prevents a generated placeholder from replacing it
        # or being cached as album artwork.
        return None

    @staticmethod
    def _image_to_rgb565(raw: bytes, width: int, height: int) -> bytes:
        with Image.open(BytesIO(raw)) as source:
            source_rgb = source.convert("RGB")
            fitted = ImageOps.contain(
                source_rgb,
                (width, height),
                method=Image.Resampling.LANCZOS,
            )

            image = Image.new("RGB", (width, height))
            left = (width - fitted.width) // 2
            top = (height - fitted.height) // 2
            image.paste(fitted, (left, top))

            output = bytearray(width * height * 2)
            write_offset = 0

            for red, green, blue in image.getdata():
                pixel = (
                    ((red & 0xF8) << 8)
                    | ((green & 0xFC) << 3)
                    | (blue >> 3)
                )
                struct.pack_into("<H", output, write_offset, pixel)
                write_offset += 2

        return bytes(output)

    @staticmethod
    def _cache_key(
        title: str,
        artist: str,
        album: str,
        width: int,
        height: int,
    ) -> tuple[str, str, str, int, int]:
        clean_title = _clean_search_text(title).casefold()
        clean_artist = _clean_search_text(artist).casefold()
        clean_album = _clean_search_text(album).casefold()

        # Album artwork is normally shared by every song on the album.
        # Use the title only when Spotify supplies no album name.
        identity_kind = "album" if clean_album else "track"
        identity_value = clean_album if clean_album else clean_title

        return (
            identity_kind,
            clean_artist,
            identity_value,
            width,
            height,
        )

    @staticmethod
    def _cache_path(
        cache_key: tuple[str, str, str, int, int],
    ) -> Path:
        packed = "\x1f".join(
            (
                CACHE_SCHEMA_VERSION,
                cache_key[0],
                cache_key[1],
                cache_key[2],
                str(cache_key[3]),
                str(cache_key[4]),
            )
        ).encode("utf-8")
        digest = hashlib.sha256(packed).hexdigest()
        return (
            CACHE_DIR
            / f"{digest}_{cache_key[3]}x{cache_key[4]}.rgb565"
        )

    @staticmethod
    def _read_disk_cache(
        path: Path,
        expected_size: int,
    ) -> bytes | None:
        try:
            data = path.read_bytes()
        except OSError:
            return None

        if len(data) != expected_size:
            try:
                path.unlink()
            except OSError:
                pass
            return None
        return data

    @staticmethod
    def _write_disk_cache(path: Path, artwork: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(artwork)
        temporary.replace(path)

    def _remember(
        self,
        cache_key: tuple[str, str, str, int, int],
        artwork: bytes,
    ) -> None:
        if cache_key in self._artwork_cache:
            self._artwork_cache.pop(cache_key)
        elif len(self._artwork_cache) >= MEMORY_CACHE_LIMIT:
            oldest_key = next(iter(self._artwork_cache))
            self._artwork_cache.pop(oldest_key, None)

        self._artwork_cache[cache_key] = artwork

    async def get_cached_album_art_rgb565_for_track(
        self,
        title: str,
        artist: str,
        album: str,
        width: int = 210,
        height: int = 210,
    ) -> bytes | None:
        """Return cached artwork only; never perform a network request."""
        cache_key = self._cache_key(
            title,
            artist,
            album,
            width,
            height,
        )
        expected_size = width * height * 2

        memory_cached = self._artwork_cache.get(cache_key)
        if memory_cached is not None:
            self._remember(cache_key, memory_cached)
            _log(
                f"Immediate memory cache hit for "
                f"{title!r} / {artist!r} / {album!r}"
            )
            return memory_cached

        cache_path = self._cache_path(cache_key)
        disk_cached = await asyncio.to_thread(
            self._read_disk_cache,
            cache_path,
            expected_size,
        )
        if disk_cached is not None:
            self._remember(cache_key, disk_cached)
            _log(
                f"Immediate disk cache hit for "
                f"{title!r} / {artist!r} / {album!r}"
            )
            return disk_cached

        return None

    async def get_album_art_rgb565_for_track(
        self,
        title: str,
        artist: str,
        album: str,
        width: int = 210,
        height: int = 210,
    ) -> bytes | None:
        title = title.strip()
        artist = artist.strip()
        album = album.strip()

        if not title or not artist:
            return None

        cached = await self.get_cached_album_art_rgb565_for_track(
            title,
            artist,
            album,
            width,
            height,
        )
        if cached is not None:
            return cached

        cache_key = self._cache_key(
            title,
            artist,
            album,
            width,
            height,
        )
        expected_size = width * height * 2

        _log(f"Cache miss for {title!r} / {artist!r} / {album!r}")

        raw = await asyncio.to_thread(
            self._find_cover_bytes_sync,
            title,
            artist,
            album,
        )
        if raw is None:
            return None

        artwork = await asyncio.to_thread(
            self._image_to_rgb565,
            raw,
            width,
            height,
        )

        if len(artwork) != expected_size:
            raise RuntimeError(
                f"RGB565 conversion produced {len(artwork)} bytes; "
                f"expected {expected_size}."
            )

        cache_path = self._cache_path(cache_key)
        try:
            await asyncio.to_thread(
                self._write_disk_cache,
                cache_path,
                artwork,
            )
            _log(f"Saved disk cache: {cache_path.name}")
        except OSError as exc:
            _log(f"Could not save disk cache: {exc}")

        self._remember(cache_key, artwork)
        _log(
            f"RGB565 artwork ready for {title!r} / {artist!r}: "
            f"{len(artwork)} bytes"
        )
        return artwork

    async def get_album_art_rgb565(
        self,
        width: int = 210,
        height: int = 210,
    ) -> bytes | None:
        session = await self._select_active_media_session()
        if session is None:
            return None

        media_properties = await session.try_get_media_properties_async()
        return await self.get_album_art_rgb565_for_track(
            media_properties.title or "",
            media_properties.artist or "",
            media_properties.album_title or "",
            width,
            height,
        )
