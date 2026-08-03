from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class QueueItem:
    title: str
    subtitle: str = ""


@dataclass(slots=True)
class SourceCapabilities:
    play_pause: bool = True
    previous: bool = False
    next: bool = False
    queue: bool = False
    volume: bool = True
    extra_actions: list[str] = field(default_factory=list)


class MediaSourcePlugin(Protocol):
    @property
    def name(self) -> str: ...

    def capabilities(self) -> SourceCapabilities: ...

    def queue(self) -> list[QueueItem]: ...
