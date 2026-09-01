from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://lrclib.net/api/get"
USER_AGENT = "SpotifyControllerDisplay/8.0 (personal desktop display)"
TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")


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
                "album_name": album.strip(),
                "duration": int(duration_seconds),
            }
        )
        request = Request(
            f"{API_URL}?{query}",
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

        if payload.get("instrumental"):
            return Lyrics(status="Instrumental")

        lines = parse_synced_lyrics(payload.get("syncedLyrics") or "")
        if not lines:
            return Lyrics(status="Synced lyrics unavailable")
        return Lyrics(lines=lines, status="")
