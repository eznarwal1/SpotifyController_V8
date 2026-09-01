from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://lrclib.net/api"
USER_AGENT = "SpotifyControllerDisplay/8.0 (personal desktop display)"
TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
ROMANIZED_MARKERS = ("romanized", "romanised", "romanization", "romaji")


@dataclass(frozen=True, slots=True)
class LyricLine:
    start_seconds: float
    text: str


@dataclass(frozen=True, slots=True)
class Lyrics:
    lines: tuple[LyricLine, ...] = ()
    status: str = "Lyrics unavailable"

    def active_index(self, position_seconds: int | float) -> int:
        if not self.lines:
            return -1
        starts = [line.start_seconds for line in self.lines]
        return max(0, bisect_right(starts, float(position_seconds)) - 1)


def parse_synced_lyrics(value: str) -> tuple[LyricLine, ...]:
    parsed: list[LyricLine] = []

    for raw_line in str(value or "").splitlines():
        matches = list(TIMESTAMP.finditer(raw_line))
        text = TIMESTAMP.sub("", raw_line).strip()
        if not matches or not text:
            continue

        for match in matches:
            fraction = (match.group(3) or "0")
            fraction_seconds = int(fraction) / (10 ** len(fraction))
            parsed.append(
                LyricLine(
                    int(match.group(1)) * 60
                    + int(match.group(2))
                    + fraction_seconds,
                    text,
                )
            )

    return tuple(sorted(parsed, key=lambda line: line.start_seconds))


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def select_best_record(
    records: object,
    title: str,
    artist: str,
    duration_seconds: int,
) -> dict | None:
    if not isinstance(records, list):
        return None

    wanted_title = _normalized(title)
    wanted_artist = _normalized(artist)
    ranked: list[tuple[tuple[int, int, int], dict]] = []

    for record in records:
        if not isinstance(record, dict) or not record.get("syncedLyrics"):
            continue

        record_title = _normalized(record.get("trackName"))
        record_artist = _normalized(record.get("artistName"))
        metadata_score = 0
        metadata_score += 400 if record_title == wanted_title else 0
        metadata_score += 300 if record_artist == wanted_artist else 0

        try:
            difference = abs(float(record.get("duration", 0)) - duration_seconds)
        except (TypeError, ValueError):
            difference = 999.0
        metadata_score += max(0, 200 - int(difference * 25))

        labels = " ".join(
            str(record.get(field, "")).casefold()
            for field in ("trackName", "albumName")
        )
        is_romanized = any(marker in labels for marker in ROMANIZED_MARKERS)
        lyrics_text = str(record.get("syncedLyrics") or "")
        native_characters = sum(
            character.isalpha() and ord(character) > 0x024F
            for character in lyrics_text
        )

        ranked.append(
            ((metadata_score, 0 if is_romanized else 1, native_characters), record)
        )

    return max(ranked, default=(None, None), key=lambda item: item[0])[1]


class LyricsClient:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str, int], Lyrics] = {}

    def get(
        self,
        title: str,
        artist: str,
        album: str,
        duration_seconds: int,
    ) -> Lyrics:
        key = (
            title.strip().casefold(),
            artist.strip().casefold(),
            album.strip().casefold(),
            max(0, int(duration_seconds)),
        )
        if key in self._cache:
            return self._cache[key]

        lyrics = self._fetch(title, artist, album, duration_seconds)
        self._cache[key] = lyrics
        return lyrics

    @staticmethod
    def _fetch(
        title: str,
        artist: str,
        album: str,
        duration_seconds: int,
    ) -> Lyrics:
        if not title.strip() or not artist.strip() or duration_seconds <= 0:
            return Lyrics(status="Track details unavailable")

        query = urlencode(
            {
                "track_name": title.strip(),
                "artist_name": artist.strip(),
            }
        )
        request = Request(
            f"{API_URL}/search?{query}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

        try:
            with urlopen(request, timeout=12.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return Lyrics(
                status="Lyrics unavailable" if exc.code == 404 else "Lyrics service error"
            )
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            return Lyrics(status="Lyrics service unavailable")

        record = select_best_record(
            payload,
            title,
            artist,
            duration_seconds,
        )
        if record is None:
            return Lyrics(status="Synced lyrics unavailable")

        if record.get("instrumental"):
            return Lyrics(status="Instrumental")

        lines = parse_synced_lyrics(record.get("syncedLyrics") or "")
        if not lines:
            return Lyrics(status="Synced lyrics unavailable")
        return Lyrics(lines=lines, status="")
