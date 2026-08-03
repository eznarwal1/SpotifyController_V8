from __future__ import annotations

import struct

from PIL import Image, ImageEnhance, ImageFilter


BACKGROUND_WIDTH = 800
BACKGROUND_HEIGHT = 480


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
