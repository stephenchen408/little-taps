"""Draws the app icon (four toy blocks on teal) as PNGs for the home-screen app.
Run: tools/.venv/Scripts/python tools/make_icons.py"""
import pathlib
import struct
import zlib

import numpy as np

out = pathlib.Path(__file__).parent.parent / "site" / "icons"
out.mkdir(parents=True, exist_ok=True)

BG, INK = (159, 227, 216), (23, 58, 94)
BLOCKS = [(255, 107, 87), (255, 201, 60), (77, 168, 255), (92, 203, 95)]


def rounded_rect(img, x0, y0, x1, y1, r, color):
    h, w, _ = img.shape
    yy, xx = np.mgrid[0:h, 0:w]
    inside = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
    for cx, cy in [(x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)]:
        corner = ((xx < x0 + r) | (xx >= x1 - r)) & ((yy < y0 + r) | (yy >= y1 - r))
        near = (np.abs(xx - cx) <= r) & (np.abs(yy - cy) <= r)
        inside &= ~(corner & near & ((xx - cx) ** 2 + (yy - cy) ** 2 > r * r))
    img[inside] = color


def draw(size, pad_frac):
    img = np.zeros((size, size, 3), np.uint8); img[:] = BG
    pad = size * pad_frac
    cell = (size - 2 * pad) / 2
    gap, b = cell * 0.1, max(2, size * 0.022)
    for i, col in enumerate(BLOCKS):
        x = pad + (i % 2) * cell + gap / 2
        y = pad + (i // 2) * cell + gap / 2
        w = cell - gap
        r = w * 0.22
        rounded_rect(img, x, y + size * 0.03, x + w, y + w + size * 0.03, r, INK)          # drop shadow
        rounded_rect(img, x, y, x + w, y + w, r, INK)                                     # outline
        rounded_rect(img, x + b, y + b, x + w - b, y + w - b, r - b, col)                 # block
        rounded_rect(img, x + w * .18, y + w * .14, x + w * .42, y + w * .26, w * .06, (255, 255, 255))  # shine
    return img


def png(path, img):
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(data)


for size in (180, 192, 512):
    png(out / f"icon-{size}.png", draw(size, 0.14))
png(out / "icon-maskable-512.png", draw(512, 0.24))  # extra margin for Android's round masks
print("icons written to", out)
