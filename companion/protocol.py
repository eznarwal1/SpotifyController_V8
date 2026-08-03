from __future__ import annotations

import json
import struct
import zlib
from typing import Any

from ui_state import AppState


PROTOCOL_MAGIC = b"SPV2"
PROTOCOL_VERSION = 2
PACKET_TYPE_ARTWORK_RGB565 = 1
PACKET_TYPE_METADATA_RGB565 = 2
PACKET_TYPE_SOURCE_RGB565 = 3
PACKET_TYPE_VIEW_RGB565 = 4
PACKET_TYPE_BACKGROUND_RGB565 = 5

# magic, version, type, width, height, payload length, CRC-32
ARTWORK_HEADER = struct.Struct("<4sBBHHII")


def make_state_message(state: AppState) -> str:
    """Create one newline-delimited JSON state message for the ESP32."""
    media = state.media
    playback_status = str(media.playback_status).strip().lower()
    playing = playback_status == "playing"

    payload = {
        "type": "state",
        "spotify_connected": bool(state.spotify_connected),
        "application": media.application or "Media",
        "title": media.title or "",
        "artist": media.artist or "",
        "album": media.album or "",
        "playing": playing,
        "playback_status": media.playback_status,
        "position_ms": max(0, int(media.position_seconds)) * 1000,
        "duration_ms": max(0, int(media.duration_seconds)) * 1000,
        "shuffle": bool(media.shuffle_active),
        "repeat": media.repeat_mode,
        "volume": max(0, min(100, int(state.volume))),
        "muted": bool(state.muted),
        "discord_call_active": bool(state.discord_call_active),
        "discord_muted": bool(state.discord_muted),
        "discord_deafened": bool(state.discord_deafened),
        "battery_present": bool(state.battery_present),
        "battery_percent": max(0, min(100, int(state.battery_percent))),
        "battery_charging": bool(state.battery_charging),
        "view_mode": getattr(state, "view_mode", "now_playing"),
        "notification_text": getattr(state, "notification_text", ""),
        "queue_source": getattr(state, "queue_source", ""),
        "queue_entries": list(getattr(state, "queue_entries", []))[:8],
        "queue_selected_index": max(
            0,
            int(getattr(state, "queue_selected_index", 0)),
        ),
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _make_rgb565_packet(
    packet_type: int,
    rgb565_bytes: bytes,
    width: int,
    height: int,
) -> bytes:
    """Create one CRC-protected Protocol V2 RGB565 packet."""
    expected = int(width) * int(height) * 2

    if expected <= 0:
        raise ValueError("Artwork dimensions must be positive.")

    if len(rgb565_bytes) != expected:
        raise ValueError(
            f"Artwork contains {len(rgb565_bytes)} bytes; expected {expected}."
        )

    crc = zlib.crc32(rgb565_bytes) & 0xFFFFFFFF
    header = ARTWORK_HEADER.pack(
        PROTOCOL_MAGIC,
        PROTOCOL_VERSION,
        int(packet_type),
        int(width),
        int(height),
        len(rgb565_bytes),
        crc,
    )
    return header + rgb565_bytes


def parse_command_message(line: str) -> dict[str, Any] | None:
    """Parse one JSON command line received from the ESP32."""
    if not isinstance(line, str):
        return None

    line = line.strip()
    if not line:
        return None

    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return None

    if not isinstance(message, dict) or message.get("type") != "command":
        return None

    command = message.get("command")
    if not isinstance(command, str) or not command.strip():
        return None

    message["command"] = command.strip()
    return message


def make_artwork_packet(
    rgb565_bytes: bytes,
    width: int,
    height: int,
) -> bytes:
    return _make_rgb565_packet(
        PACKET_TYPE_ARTWORK_RGB565,
        rgb565_bytes,
        width,
        height,
    )


def make_metadata_packet(
    rgb565_bytes: bytes,
    width: int,
    height: int,
) -> bytes:
    return _make_rgb565_packet(
        PACKET_TYPE_METADATA_RGB565,
        rgb565_bytes,
        width,
        height,
    )


def make_source_packet(
    rgb565_bytes: bytes,
    width: int,
    height: int,
) -> bytes:
    return _make_rgb565_packet(
        PACKET_TYPE_SOURCE_RGB565,
        rgb565_bytes,
        width,
        height,
    )


def make_view_packet(
    rgb565_bytes: bytes,
    width: int,
    height: int,
) -> bytes:
    return _make_rgb565_packet(
        PACKET_TYPE_VIEW_RGB565,
        rgb565_bytes,
        width,
        height,
    )


def make_background_packet(
    rgb565_bytes: bytes,
    width: int,
    height: int,
) -> bytes:
    return _make_rgb565_packet(
        PACKET_TYPE_BACKGROUND_RGB565,
        rgb565_bytes,
        width,
        height,
    )
