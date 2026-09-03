from __future__ import annotations

import os
import struct
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from metadata_renderer import ui_background_crop

WIDTH = 600
HEIGHT = 300


def _fonts() -> Iterable[Path]:
    root = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in (
        "ARIALUNI.ttf",
        "msyh.ttc",
        "malgun.ttf",
        "meiryo.ttc",
        "segoeui.ttf",
        "arial.ttf",
    ):
        yield root / name


@lru_cache(maxsize=8)
def _font(size: int):
    for path in _fonts():
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _rgb565(image: Image.Image) -> bytes:
    image = image.convert("RGB")
    output = bytearray(image.width * image.height * 2)
    offset = 0

    for red, green, blue in image.getdata():
        value = (
            ((red & 0xF8) << 8)
            | ((green & 0xFC) << 3)
            | (blue >> 3)
        )
        struct.pack_into("<H", output, offset, value)
        offset += 2

    return bytes(output)


def _truncate(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int,
    font,
) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def render_view(
    *,
    view: str,
    theme: dict,
    queue: list[str],
    queue_index: int,
    queue_source: str,
    queue_available: bool,
    queue_status: str,
    mixer: list,
    mixer_index: int,
    themes: list[tuple[str, dict]],
    theme_index: int,
    lyric_lines: tuple[str, ...] = (),
    lyric_active_index: int = -1,
    lyric_status: str = "",
) -> bytes:
    bg = tuple(theme["background"])
    panel = tuple(theme["panel"])
    primary = tuple(theme["primary"])
    secondary = tuple(theme["secondary"])
    accent = tuple(theme["accent"])

    image = (
        ui_background_crop(100, 90, WIDTH, HEIGHT)
        if view == "lyrics"
        else Image.new("RGB", (WIDTH, HEIGHT), bg)
    )
    draw = ImageDraw.Draw(image)
    title_font = _font(24)
    row_font = _font(17)
    small_font = _font(14)
    lyric_font = _font(22)
    headings = {
        "queue": "Queue",
        "lyrics": "Lyrics",
    }
    if view == "lyrics":
        title_font = _font(28)
        draw.text(
            (18, 4),
            "Lyrics",
            fill=primary,
            font=title_font,
        )
        draw.line((18, 42, WIDTH - 18, 42), fill=panel, width=2)
    else:
        draw.text((8, 4), headings.get(view, "Now Playing"), fill=primary, font=title_font)
        draw.line((8, 36, WIDTH - 8, 36), fill=panel, width=2)

    if view == "lyrics":
        if not lyric_lines:
            message = lyric_status or "Lyrics unavailable"
            message = _truncate(draw, message, WIDTH - 24, row_font)
            draw.text(
                (18, 82),
                message,
                fill=secondary,
                font=lyric_font,
            )
        else:
            active = max(0, min(lyric_active_index, len(lyric_lines) - 1))
            start = max(0, active - 2)
            start = min(start, max(0, len(lyric_lines) - 6))
            visible = range(start, min(len(lyric_lines), start + 6))
            y = 55
            for index in visible:
                line = _truncate(draw, lyric_lines[index], WIDTH - 36, lyric_font)
                draw.text(
                    (18, y),
                    line,
                    fill=accent if index == active else secondary,
                    font=lyric_font,
                )
                y += 40

    elif view == "queue":
        source_text = queue_source or "Current source"
        draw.text(
            (12, 42),
            _truncate(draw, source_text, WIDTH - 24, small_font),
            fill=accent if queue_available else secondary,
            font=small_font,
        )

        if not queue:
            draw.text(
                (12, 68),
                _truncate(draw, queue_status, WIDTH - 24, row_font),
                fill=secondary,
                font=row_font,
            )
        else:
            start = max(0, min(queue_index, len(queue) - 1) - 1)
            for row, item in enumerate(queue[start:start + 3]):
                index = start + row
                y = 62 + row * 27
                selected = index == min(queue_index, len(queue) - 1)
                if selected:
                    draw.rounded_rectangle((6, y - 2, WIDTH - 6, y + 23), radius=7, fill=panel)
                prefix = "▶ " if selected else "   "
                text = _truncate(draw, prefix + item, WIDTH - 24, row_font)
                draw.text((12, y), text, fill=accent if selected else primary, font=row_font)

    # themes page removed; themes data is not rendered as a page

    if view != "lyrics":
        draw.text(
            (8, HEIGHT - 18),
            "Use the on-screen controls below",
            fill=secondary,
            font=small_font,
        )
    return _rgb565(image)
