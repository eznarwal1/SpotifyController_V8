from background_renderer import render_and_cache_blurred_background

# create a simple red square in RGB565
w, h = 200, 200
pixels = []
for _ in range(w * h):
    r = 255
    g = 0
    b = 0
    value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    pixels.append(value)

import struct
buf = bytearray()
for v in pixels:
    buf += struct.pack('<H', v)

digest, bg = render_and_cache_blurred_background(bytes(buf), w, h)
print('digest=', digest)
print('bg len=', len(bg))
