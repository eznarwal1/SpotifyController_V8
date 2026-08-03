from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(slots=True)
class MediaState:
    application: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    playback_status: str = "Unknown"
    position_seconds: int = 0
    duration_seconds: int = 0
    shuffle_active: bool = False
    repeat_mode: str = "None"

    @property
    def is_playing(self) -> bool:
        return self.playback_status.lower() == "playing"

@dataclass(slots=True)
class AppState:
    media: MediaState = field(default_factory=MediaState)
    volume: int = 0
    muted: bool = False
    spotify_connected: bool = False
    display_connected: bool = False
    display_port: str = ""
    discord_call_active: bool = False
    discord_muted: bool = False
    discord_deafened: bool = False
    battery_present: bool = False
    battery_percent: int = 0
    battery_charging: bool = False
    view_mode: str = "now_playing"
    notification_text: str = ""
    queue_source: str = ""
    queue_entries: list[str] = field(default_factory=list)
    queue_selected_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
