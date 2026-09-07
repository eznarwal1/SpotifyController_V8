from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8765
TAB_STALE_SECONDS = 1.5


@dataclass(slots=True)
class ChromeTab:
    tab_id: int
    window_id: int
    title: str
    url: str
    favicon_url: str
    playing: bool
    muted: bool
    position_seconds: int
    duration_seconds: int
    media_title: str
    media_artist: str
    media_album: str
    discord_call_active: bool
    discord_muted: bool
    discord_deafened: bool
    discord_evidence: str
    discord_server: str
    discord_channel: str
    discord_messages: list[str]
    queue_source: str
    queue_available: bool
    queue_status: str
    queue_items: list[str]
    spotify_shuffle_active: bool
    spotify_repeat_mode: str
    received_at: float

    @property
    def source_label(self) -> str:
        title = self.media_title.strip() or self.title.strip() or "Chrome tab"
        return f"Chrome — {title}"

    @property
    def display_title(self) -> str:
        return self.media_title.strip() or self.title.strip() or "Chrome media"

    @property
    def display_artist(self) -> str:
        if self.media_artist.strip():
            return self.media_artist.strip()

        host = urlparse(self.url).hostname or "Chrome"
        return host.removeprefix("www.")

    @property
    def display_album(self) -> str:
        return self.media_album.strip() or "Chrome tab"


class ChromeBridge:
    """Local-only bridge between the Chrome extension and the companion."""

    def __init__(self) -> None:
        self._tabs: dict[int, ChromeTab] = {}
        self._commands: dict[int, list[str]] = {}
        self._lock = threading.RLock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            return

        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(
                self,
                status: int,
                payload: dict[str, Any],
            ) -> None:
                encoded = json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")

                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type",
                )
                self.send_header(
                    "Access-Control-Allow-Methods",
                    "GET,POST,OPTIONS",
                )
                self.end_headers()
                self.wfile.write(encoded)

            def do_OPTIONS(self) -> None:
                self._send_json(200, {"ok": True})

            def do_GET(self) -> None:
                parsed = urlparse(self.path)

                if parsed.path == "/health":
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "service": "SpotifyController Chrome Bridge",
                        },
                    )
                    return

                if parsed.path == "/commands":
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "commands": bridge.pop_all_commands(),
                        },
                    )
                    return

                self._send_json(404, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:
                parsed = urlparse(self.path)

                if parsed.path != "/tabs":
                    self._send_json(404, {"ok": False, "error": "not_found"})
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length)
                    payload = json.loads(raw.decode("utf-8"))
                    tabs = payload.get("tabs", [])
                    if not isinstance(tabs, list):
                        raise ValueError("tabs must be a list")
                    bridge.update_tabs(tabs)
                except Exception as exc:
                    logging.exception("ChromeBridge: failed to process /tabs POST")
                    self._send_json(
                        400,
                        {
                            "ok": False,
                            "error": type(exc).__name__,
                            "detail": str(exc),
                        },
                    )
                    return

                self._send_json(
                    200,
                    {
                        "ok": True,
                        "tab_count": len(bridge.list_tabs()),
                    },
                )

            def log_message(self, format: str, *args: object) -> None:
                # Keep the companion terminal clean.
                return

        try:
            self._server = ThreadingHTTPServer((HOST, PORT), Handler)
        except OSError as exc:
            raise RuntimeError(
                f"Could not start Chrome bridge on {HOST}:{PORT}: {exc}"
            ) from exc

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="ChromeBridgeServer",
            daemon=True,
        )
        self._thread.start()

    def update_tabs(self, raw_tabs: list[dict[str, Any]]) -> None:
        now = time.monotonic()
        updated: dict[int, ChromeTab] = {}

        for raw in raw_tabs:
            try:
                tab_id = int(raw["tab_id"])
            except (KeyError, TypeError, ValueError):
                continue

            updated[tab_id] = ChromeTab(
                tab_id=tab_id,
                window_id=int(raw.get("window_id", 0)),
                title=str(raw.get("title", "")),
                url=str(raw.get("url", "")),
                favicon_url=str(raw.get("favicon_url", "")),
                playing=bool(raw.get("playing", False)),
                muted=bool(raw.get("muted", False)),
                position_seconds=max(
                    0,
                    int(float(raw.get("position_seconds", 0) or 0)),
                ),
                duration_seconds=max(
                    0,
                    int(float(raw.get("duration_seconds", 0) or 0)),
                ),
                media_title=str(raw.get("media_title", "")),
                media_artist=str(raw.get("media_artist", "")),
                media_album=str(raw.get("media_album", "")),
                discord_call_active=bool(raw.get("discord_call_active", False)),
                discord_muted=bool(raw.get("discord_muted", False)),
                discord_deafened=bool(raw.get("discord_deafened", False)),
                discord_evidence=str(raw.get("discord_evidence", "")),
                discord_server=str(raw.get("discord_server", "")),
                discord_channel=str(raw.get("discord_channel", "")),
                discord_messages=[
                    (
                        f"{str(item.get('author', '')).strip()}: "
                        f"{str(item.get('text', '')).strip()}"
                    ).strip(": ")
                    for item in raw.get("discord_messages", [])
                    if isinstance(item, dict)
                    and str(item.get("text", "")).strip()
                ][:8],
                queue_source=str(raw.get("queue_source", "")),
                queue_available=bool(raw.get("queue_available", False)),
                queue_status=str(raw.get("queue_status", "")),
                queue_items=[
                    str(item) for item in raw.get("queue_items", [])
                    if str(item).strip()
                ][:250],
                spotify_shuffle_active=bool(
                    raw.get("spotify_shuffle_active", False)
                ),
                spotify_repeat_mode=str(
                    raw.get("spotify_repeat_mode", "None")
                ),
                received_at=now,
            )

        with self._lock:
            self._tabs = updated

    def list_tabs(self) -> list[ChromeTab]:
        now = time.monotonic()

        with self._lock:
            stale_ids = [
                tab_id
                for tab_id, tab in self._tabs.items()
                if now - tab.received_at > TAB_STALE_SECONDS
            ]
            for tab_id in stale_ids:
                self._tabs.pop(tab_id, None)
                self._commands.pop(tab_id, None)

            tabs = list(self._tabs.values())

        # Keep source-switch order stable when playback moves between tabs.
        # Tab IDs remain fixed for the lifetime of each Chrome tab, while
        # playing state and media titles change constantly.
        return sorted(tabs, key=lambda tab: tab.tab_id)

    def get_tab(self, tab_id: int) -> ChromeTab | None:
        for tab in self.list_tabs():
            if tab.tab_id == tab_id:
                return tab
        return None

    def enqueue_command(self, tab_id: int, command: str) -> bool:
        if self.get_tab(tab_id) is None:
            return False

        with self._lock:
            self._commands.setdefault(tab_id, []).append(command)
        return True

    def pop_all_commands(self) -> dict[str, list[str]]:
        with self._lock:
            result = {
                str(tab_id): commands[:]
                for tab_id, commands in self._commands.items()
                if commands
            }
            self._commands.clear()
        return result

    def selected_or_playing_tab(self) -> ChromeTab | None:
        tabs = self.list_tabs()
        playing = [tab for tab in tabs if tab.playing]

        # Prefer supported queue sources when multiple tabs exist.
        supported_playing = [
            tab for tab in playing if tab.queue_source
        ]
        if supported_playing:
            return supported_playing[0]

        if playing:
            return playing[0]

        supported = [tab for tab in tabs if tab.queue_source]
        return supported[0] if supported else (tabs[0] if tabs else None)

    def selected_or_playing_queue(self) -> list[str]:
        tab = self.selected_or_playing_tab()
        return [] if tab is None else list(tab.queue_items)

    def selected_queue_status(self) -> tuple[str, bool, str]:
        tab = self.selected_or_playing_tab()

        if tab is None:
            return "", False, "No browser media source detected"

        return (
            tab.queue_source,
            tab.queue_available,
            tab.queue_status,
        )


    def activate_queue_item(self, index: int) -> bool:
        tab = self.selected_or_playing_tab()

        if tab is None:
            return False

        return self.enqueue_command(
            tab.tab_id,
            f"queue_play:{max(0, int(index))}",
        )


    def get_discord_tab(
        self,
        *,
        require_active_call: bool = False,
    ) -> ChromeTab | None:
        tabs = [
            tab
            for tab in self.list_tabs()
            if "discord.com" in tab.url.casefold()
            or "discord" in tab.title.casefold()
        ]

        active = [
            tab
            for tab in tabs
            if tab.discord_call_active
        ]

        if active:
            return active[0]

        if require_active_call:
            return None

        return tabs[0] if tabs else None

    def discord_status(self) -> tuple[bool, bool, bool]:
        tab = self.get_discord_tab()
        if tab is None:
            return False, False, False
        return (
            tab.discord_call_active,
            tab.discord_muted,
            tab.discord_deafened,
        )

    def discord_message_snapshot(
        self,
    ) -> tuple[str, str, list[str]]:
        tab = self.get_discord_tab()
        if tab is None:
            return "", "", []

        return (
            tab.discord_server,
            tab.discord_channel,
            list(tab.discord_messages),
        )

    def enqueue_discord_command(self, command: str) -> bool:
        tab = self.get_discord_tab(require_active_call=True)

        if tab is None:
            return False

        return self.enqueue_command(tab.tab_id, command)


_bridge = ChromeBridge()


def get_chrome_bridge() -> ChromeBridge:
    return _bridge
