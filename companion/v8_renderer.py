from __future__ import annotations

import os
import struct
from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 470
HEIGHT = 160


def _fonts() -> Iterable[Path]:
    root = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in (
        "segoeui.ttf",
        "msyh.ttc",
        "malgun.ttf",
        "meiryo.ttc",
    ):
        yield root / name


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
    brightness: int = 50,
) -> bytes:
    bg = tuple(theme["background"])
    panel = tuple(theme["panel"])
    primary = tuple(theme["primary"])
    secondary = tuple(theme["secondary"])
    accent = tuple(theme["accent"])

    image = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(image)
    title_font = _font(24)
    row_font = _font(17)
    small_font = _font(14)

    headings = {
        "queue": "Queue",
        "settings": "Settings",
    }
    draw.text((8, 4), headings.get(view, "Now Playing"), fill=primary, font=title_font)
    draw.line((8, 36, WIDTH - 8, 36), fill=panel, width=2)

    if view == "queue":
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

    elif view == "settings":
        brightness = max(0, min(100, int(brightness)))
        draw.text((12, 54), f"Brightness: {brightness}%", fill=primary, font=row_font)
        # Draw a simple slider representation
        slider_x = 12
        slider_y = 80
        slider_w = WIDTH - 24
        slider_h = 18
        draw.rounded_rectangle((slider_x, slider_y, slider_x + slider_w, slider_y + slider_h), radius=6, fill=panel)
        knob_x = slider_x + int(slider_w * (brightness / 100.0))
        knob_w = 12
        draw.ellipse((knob_x - knob_w//2, slider_y - 6, knob_x + knob_w//2, slider_y + slider_h + 6), fill=accent)


    # themes page removed; themes data is not rendered as a page

    draw.text(
        (8, HEIGHT - 18),
        "Use the on-screen controls below",
        fill=secondary,
        font=small_font,
    )
    return _rgb565(image)
