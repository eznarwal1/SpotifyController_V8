from __future__ import annotations

import os
import struct
import threading
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PANEL_WIDTH = 470
PANEL_HEIGHT = 118
BACKGROUND = (18, 18, 18)
TITLE_COLOR = (255, 255, 255)
ARTIST_COLOR = (190, 190, 190)
ALBUM_COLOR = (130, 130, 130)
SOURCE_COLOR = (180, 180, 180)

WINDOWS_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


@dataclass(slots=True)
class MetadataPanel:
    title: str
    artist: str
    album: str
    source: str


def _contains_korean(text: str) -> bool:
    return any(
        "\u1100" <= char <= "\u11FF"
        or "\u3130" <= char <= "\u318F"
        or "\uAC00" <= char <= "\uD7AF"
        for char in text
    )


def _contains_japanese(text: str) -> bool:
    return any(
        "\u3040" <= char <= "\u30FF"
        or "\u31F0" <= char <= "\u31FF"
        for char in text
    )


def _contains_cjk(text: str) -> bool:
    return any(
        "\u3400" <= char <= "\u4DBF"
        or "\u4E00" <= char <= "\u9FFF"
        or "\uF900" <= char <= "\uFAFF"
        for char in text
    )


def _font_candidates(text: str) -> list[Path]:
    """
    Prefer a font that actually covers the script in the current line.

    The prior version selected Segoe UI first. Segoe UI does not contain most
    CJK/Hangul glyphs, so Pillow rendered empty boxes even though the metadata
    remained valid Unicode.
    """
    if _contains_korean(text):
        names = (
            "malgun.ttf",
            "malgunbd.ttf",
            "NotoSansKR-Regular.ttf",
            "msyh.ttc",
            "meiryo.ttc",
            "seguiemj.ttf",
            "segoeui.ttf",
        )
    elif _contains_japanese(text):
        names = (
            "meiryo.ttc",
            "meiryob.ttc",
            "msgothic.ttc",
            "NotoSansJP-Regular.ttf",
            "msyh.ttc",
            "malgun.ttf",
            "seguiemj.ttf",
            "segoeui.ttf",
        )
    elif _contains_cjk(text):
        names = (
            "msyh.ttc",
            "msyhbd.ttc",
            "simsun.ttc",
            "simhei.ttf",
            "NotoSansCJKsc-Regular.otf",
            "meiryo.ttc",
            "malgun.ttf",
            "seguiemj.ttf",
            "segoeui.ttf",
        )
    else:
        names = (
            "segoeui.ttf",
            "seguisb.ttf",
            "arial.ttf",
            "seguiemj.ttf",
            "msyh.ttc",
            "malgun.ttf",
            "meiryo.ttc",
        )

    return [WINDOWS_FONTS / name for name in names]


def _load_font(
    text: str,
    size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _font_candidates(text):
        if not candidate.exists():
            continue

        try:
            return ImageFont.truetype(str(candidate), size=size)
        except OSError:
            continue

    return ImageFont.load_default()


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    font: ImageFont.ImageFont,
) -> str:
    text = text.strip()
    if not text:
        return ""

    if draw.textlength(text, font=font) <= max_width:
        return text

    ellipsis = "…"
    low = 0
    high = len(text)

    while low < high:
        middle = (low + high + 1) // 2
        candidate = text[:middle].rstrip() + ellipsis

        if draw.textlength(candidate, font=font) <= max_width:
            low = middle
        else:
            high = middle - 1

    return text[:low].rstrip() + ellipsis


def _draw_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: tuple[int, int],
    max_width: int,
    size: int,
    fill: tuple[int, int, int],
) -> None:
    font = _load_font(text, size)
    fitted = _fit_text(draw, text, max_width, font)
    draw.text(position, fitted, fill=fill, font=font)


def _rgb565_bytes(image: Image.Image) -> bytes:
    image = image.convert("RGB")
    output = bytearray(image.width * image.height * 2)
    offset = 0

    for red, green, blue in image.getdata():
        pixel = (
            ((red & 0xF8) << 8)
            | ((green & 0xFC) << 3)
            | (blue >> 3)
        )
        struct.pack_into("<H", output, offset, pixel)
        offset += 2

    return bytes(output)


def _rgb565_to_image(
    data: bytes,
    width: int,
    height: int,
) -> Image.Image:
    expected = width * height * 2

    if len(data) != expected:
        raise ValueError(
            f"RGB565 data has {len(data)} bytes; expected {expected}."
        )

    pixels: list[tuple[int, int, int]] = []

    for offset in range(0, len(data), 2):
        value = struct.unpack_from("<H", data, offset)[0]
        red = ((value >> 11) & 0x1F) * 255 // 31
        green = ((value >> 5) & 0x3F) * 255 // 63
        blue = (value & 0x1F) * 255 // 31
        pixels.append((red, green, blue))

    image = Image.new("RGB", (width, height))
    image.putdata(pixels)
    return image


def set_ui_background(
    rgb565_bytes: bytes,
    width: int,
    height: int,
) -> int:
    """
    Store the same blurred background sent to the display.

    Metadata and source-button canvases are cropped from this image, so they
    visually blend into the full-screen background instead of drawing dark
    rectangular cutouts.
    """
    global _full_background
    global _background_revision

    background = _rgb565_to_image(
        rgb565_bytes,
        width,
        height,
    )

    if background.size != (SCREEN_WIDTH, SCREEN_HEIGHT):
        background = background.resize(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            Image.Resampling.BILINEAR,
        )

    with _background_lock:
        _full_background = background
        _background_revision += 1
        return _background_revision


def ui_background_revision() -> int:
    with _background_lock:
        return _background_revision


def _background_crop(
    x: int,
    y: int,
    width: int,
    height: int,
) -> Image.Image:
    with _background_lock:
        background = (
            None
            if _full_background is None
            else _full_background.copy()
        )

    if background is None:
        return Image.new(
            "RGB",
            (width, height),
            BACKGROUND,
        )

    return background.crop(
        (x, y, x + width, y + height)
    )


def ui_background_crop(
    x: int,
    y: int,
    width: int,
    height: int,
) -> Image.Image:
    """Return a copy of the exact background region shown by the display."""
    return _background_crop(x, y, width, height)


def render_metadata_panel(metadata: MetadataPanel) -> bytes:
    image = _background_crop(
        METADATA_X,
        METADATA_Y,
        PANEL_WIDTH,
        PANEL_HEIGHT,
    ).convert("RGB")
    draw = ImageDraw.Draw(image)

    usable = PANEL_WIDTH - 4

    _draw_line(
        draw,
        metadata.title,
        (0, 0),
        usable,
        27,
        TITLE_COLOR,
    )
    _draw_line(
        draw,
        metadata.artist,
        (0, 39),
        usable,
        19,
        ARTIST_COLOR,
    )
    _draw_line(
        draw,
        metadata.album,
        (0, 69),
        usable,
        15,
        ALBUM_COLOR,
    )
    _draw_line(
        draw,
        metadata.source,
        (0, 97),
        usable,
        13,
        SOURCE_COLOR,
    )

    return _rgb565_bytes(image)


SOURCE_WIDTH = 220
SOURCE_HEIGHT = 38
SOURCE_CANVAS = (18, 18, 18)
SOURCE_BACKGROUND = (40, 40, 40)
SOURCE_BORDER = (85, 85, 85)
SOURCE_TEXT = (255, 255, 255)

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
METADATA_X = 290
METADATA_Y = 66
SOURCE_X = 520
SOURCE_Y = 18

_background_lock = threading.RLock()
_full_background: Image.Image | None = None
_background_revision = 0


def render_source_button(source: str) -> bytes:
    """
    Render the source selector label on Windows so CJK/Hangul/Kana characters
    do not depend on the ESP32's built-in LVGL font.
    """
    image = _background_crop(
        SOURCE_X,
        SOURCE_Y,
        SOURCE_WIDTH,
        SOURCE_HEIGHT,
    ).convert("RGB")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (1, 1, SOURCE_WIDTH - 2, SOURCE_HEIGHT - 2),
        radius=18,
        fill=SOURCE_BACKGROUND,
        outline=SOURCE_BORDER,
        width=1,
    )

    text = source.strip() or "Auto"
    font = _load_font(text, 15)
    fitted = _fit_text(draw, text, SOURCE_WIDTH - 20, font)

    bbox = draw.textbbox((0, 0), fitted, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = max(10, (SOURCE_WIDTH - text_width) // 2)
    y = max(0, (SOURCE_HEIGHT - text_height) // 2 - bbox[1])

    draw.text((x, y), fitted, fill=SOURCE_TEXT, font=font)
    return _rgb565_bytes(image)
