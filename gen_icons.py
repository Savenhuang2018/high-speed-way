#!/usr/bin/env python3
"""Generate PWA icons (192x192, 512x512) - zero dependency PNG generation."""
import struct, zlib, os

def create_png(width, height, pixels):
    def make_chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    raw = b''
    for y in range(height):
        raw += b'\x00'
        raw += bytes(pixels[y * width * 4:(y + 1) * width * 4])
    idat = zlib.compress(raw, 9)
    return sig + make_chunk(b'IHDR', ihdr) + make_chunk(b'IDAT', idat) + make_chunk(b'IEND', b'')

def draw_icon(size):
    pixels = bytearray(size * size * 4)
    cx, cy = size / 2, size / 2
    for y in range(size):
        for x in range(size):
            idx = (y * size + x) * 4
            dx = max(0, abs(x - cx) - (size * 0.35))
            dy = max(0, abs(y - cy) - (size * 0.35))
            dist = (dx*dx + dy*dy) ** 0.5
            if dist > size * 0.12:
                pixels[idx:idx+4] = [0, 0, 0, 0]
                continue
            t = y / size
            r = int(255 * (1 - t * 0.1))
            g = int(107 * (1 - t * 0.1))
            b = int(53 * (1 - t * 0.1))
            road_left = int(size * 0.35)
            road_right = int(size * 0.65)
            if road_left <= x <= road_right:
                r, g, b = 255, 255, 255
                dash_h = max(1, size // 8)
                center_x = size // 2
                if abs(x - center_x) < max(1, size // 50):
                    if (y // dash_h) % 2 == 0:
                        r, g, b = 255, 107, 53
            pin_cx = size // 2
            pin_cy = int(size * 0.28)
            pin_r = size // 8
            pdx = x - pin_cx
            pdy = y - pin_cy
            pdist = (pdx*pdx + pdy*pdy) ** 0.5
            if pdist < pin_r:
                r, g, b = 255, 107, 53
                if pdist < pin_r * 0.5:
                    r, g, b = 255, 255, 255
            pixels[idx:idx+4] = [r, g, b, 255]
    return pixels

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
for size in [192, 512]:
    pixels = draw_icon(size)
    png_data = create_png(size, size, pixels)
    path = os.path.join(out_dir, f'icon-{size}.png')
    with open(path, 'wb') as f:
        f.write(png_data)
    print(f'Generated icon-{size}.png ({len(png_data)} bytes)')
print('Done')
