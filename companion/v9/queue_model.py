from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class QueueEntry:
    """Source-independent queue row used by the V9 transport and LVGL page."""

    title: str
    artist: str = ""
    source_id: str = ""

    @property
    def display_text(self) -> str:
        """Return the required display format: ``Song Name - Artist``."""
        if self.artist:
            return f"{self.title} - {self.artist}"
        return self.title


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def normalize_queue_entries(
    rows: Iterable[object],
    *,
    limit: int = 30,
) -> list[QueueEntry]:
    """
    Convert browser/source rows into stable, deduplicated queue entries.

    Accepted row forms:
    - QueueEntry
    - {"title": "...", "artist": "...", "source_id": "..."}
    - ("title", "artist")
    - "Song Name - Artist"
    """
    entries: list[QueueEntry] = []
    seen: set[tuple[str, str, str]] = set()

    for row in rows:
        if isinstance(row, QueueEntry):
            entry = row
        elif isinstance(row, dict):
            entry = QueueEntry(
                title=_clean(row.get("title")),
                artist=_clean(row.get("artist")),
                source_id=_clean(row.get("source_id")),
            )
        elif isinstance(row, (tuple, list)):
            title = _clean(row[0]) if row else ""
            artist = _clean(row[1]) if len(row) > 1 else ""
            entry = QueueEntry(title=title, artist=artist)
        else:
            text = _clean(row)
            title, separator, artist = text.partition(" - ")
            entry = QueueEntry(
                title=_clean(title),
                artist=_clean(artist) if separator else "",
            )

        if not entry.title:
            continue

        key = (
            entry.title.casefold(),
            entry.artist.casefold(),
            entry.source_id.casefold(),
        )
        if key in seen:
            continue

        seen.add(key)
        entries.append(entry)

        if len(entries) >= max(0, limit):
            break

    return entries
