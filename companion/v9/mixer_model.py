from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

MAX_MIXER_ENTRIES = 8
MAX_MIXER_NAME = 64


class MixerLike(Protocol):
    name: str
    volume: int
    muted: bool


@dataclass(frozen=True, slots=True)
class MixerEntry:
    name: str
    volume: int
    muted: bool

    @property
    def display_text(self) -> str:
        suffix = " [Muted]" if self.muted else ""
        return f"{self.name}  {self.volume}%{suffix}"


@dataclass(frozen=True, slots=True)
class MixerState:
    selected_index: int
    entries: tuple[MixerEntry, ...]


def build_mixer_state(
    sessions: Iterable[MixerLike],
    *,
    selected_index: int,
) -> MixerState:
    entries: list[MixerEntry] = []

    for session in sessions:
        name = " ".join(str(session.name or "").split())[:MAX_MIXER_NAME]

        if not name:
            continue

        entries.append(
            MixerEntry(
                name=name,
                volume=max(0, min(100, int(session.volume))),
                muted=bool(session.muted),
            )
        )

        if len(entries) >= MAX_MIXER_ENTRIES:
            break

    selected = 0 if not entries else max(
        0,
        min(int(selected_index), len(entries) - 1),
    )

    return MixerState(
        selected_index=selected,
        entries=tuple(entries),
    )