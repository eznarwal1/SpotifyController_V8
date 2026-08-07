from __future__ import annotations

import hashlib
from pathlib import Path
import struct

from PIL import Image, ImageEnhance, ImageFilter


BACKGROUND_WIDTH = 800
BACKGROUND_HEIGHT = 480
BACKGROUND_CACHE_DIR = Path(__file__).resolve().parent / "background_cache"
BACKGROUND_CACHE_VERSION = "v1"
BACKGROUND_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def background_digest(
    artwork_rgb565: bytes,
    artwork_width: int,
    artwork_height: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(BACKGROUND_CACHE_VERSION.encode("ascii"))
    digest.update(b"\0")
    digest.update(str(artwork_width).encode("ascii"))
    digest.update(b"x")
    digest.update(str(artwork_height).encode("ascii"))
    digest.update(b"\0")
    digest.update(artwork_rgb565)
    return digest.hexdigest()


def _background_cache_path(digest: str) -> Path:
    return BACKGROUND_CACHE_DIR / f"{digest}_{BACKGROUND_WIDTH}x{BACKGROUND_HEIGHT}.rgb565"


def get_cached_blurred_background(
    artwork_rgb565: bytes,
    artwork_width: int,
    artwork_height: int,
) -> tuple[str, bytes | None]:
    digest = background_digest(
        artwork_rgb565,
        artwork_width,
        artwork_height,
    )
    path = _background_cache_path(digest)
    expected_size = BACKGROUND_WIDTH * BACKGROUND_HEIGHT * 2

    try:
        data = path.read_bytes()
    except OSError:
        return digest, None

    if len(data) != expected_size:
        try:
            path.unlink()
        except OSError:
            pass
        return digest, None

    return digest, data


def render_and_cache_blurred_background(
    artwork_rgb565: bytes,
    artwork_width: int,
    artwork_height: int,
) -> tuple[str, bytes]:
    digest, cached = get_cached_blurred_background(
        artwork_rgb565,
        artwork_width,
        artwork_height,
    )
    if cached is not None:
        return digest, cached

    background = render_blurred_background(
        artwork_rgb565,
        artwork_width,
        artwork_height,
    )
    path = _background_cache_path(digest)
    temporary = path.with_suffix(path.suffix + ".tmp")

    try:
        temporary.write_bytes(background)
        temporary.replace(path)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass

    return digest, background



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


def _image_to_rgb565(image: Image.Image) -> bytes:
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


def render_blurred_background(
    artwork_rgb565: bytes,
    artwork_width: int,
    artwork_height: int,
) -> bytes:
    """
    Build the blurred background at the panel's exact 800x480 size.

    This avoids LVGL scaling/clipping and guarantees that metadata crops use
    the exact same pixels as the displayed full-screen background.
    """
    image = _rgb565_to_image(
        artwork_rgb565,
        artwork_width,
        artwork_height,
    )

    # Cover a 5:3 frame before resizing.
    target_ratio = BACKGROUND_WIDTH / BACKGROUND_HEIGHT
    source_ratio = image.width / image.height

    if source_ratio > target_ratio:
        crop_width = round(image.height * target_ratio)
        left = (image.width - crop_width) // 2
        image = image.crop(
            (left, 0, left + crop_width, image.height)
        )
    else:
        crop_height = round(image.width / target_ratio)
        top = (image.height - crop_height) // 2
        image = image.crop(
            (0, top, image.width, top + crop_height)
        )

    image = image.resize(
        (BACKGROUND_WIDTH, BACKGROUND_HEIGHT),
        Image.Resampling.LANCZOS,
    )
    image = image.filter(ImageFilter.GaussianBlur(radius=38))
    image = ImageEnhance.Contrast(image).enhance(0.82)
    image = ImageEnhance.Brightness(image).enhance(0.33)
    image = ImageEnhance.Color(image).enhance(0.78)

    return _image_to_rgb565(image)
