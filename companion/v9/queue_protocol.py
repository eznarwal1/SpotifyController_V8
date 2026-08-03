from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:
    from .queue_model import QueueEntry, normalize_queue_entries
except ImportError:
    from queue_model import QueueEntry, normalize_queue_entries


MAX_QUEUE_ENTRIES = 8
MAX_QUEUE_TEXT = 120


@dataclass(frozen=True, slots=True)
class QueueState:
    source: str
    selected_index: int
    entries: tuple[QueueEntry, ...]

    def display_rows(self) -> list[str]:
        return [
            entry.display_text[:MAX_QUEUE_TEXT]
            for entry in self.entries
        ]


def build_queue_state(
    rows: Iterable[object],
    *,
    source: str,
    selected_index: int,
) -> QueueState:
    entries = tuple(
        normalize_queue_entries(
            rows,
            limit=MAX_QUEUE_ENTRIES,
        )
    )
    selected = 0 if not entries else max(
        0,
        min(int(selected_index), len(entries) - 1),
    )
    return QueueState(
        source=" ".join(str(source or "").split())[:MAX_QUEUE_TEXT],
        selected_index=selected,
        entries=entries,
    )
