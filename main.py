#!/usr/bin/env python3
"""EMBER-1, the USB campfire.

Renders a studio catalogue photograph of an impossible gadget to
/output/entry.png.  Pure Python 3 standard library, fully deterministic.
"""

import math
import os
import random
import struct
import zlib

W = H = 1024
SEED = 20261121

# ---------------------------------------------------------------- canvas

px = bytearray(W * H * 3)


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def put(x, y, r, g, b, a):
    """Alpha-blend one pixel."""
    if a <= 0.0 or x < 0 or x >= W or y < 0 or y >= H:
        return
    i = (y * W + x) * 3
    ia = 1.0 - a
    px[i] = int(px[i] * ia + r * a + 0.5)
    px[i + 1] = int(px[i + 1] * ia + g * a + 0.5)
    px[i + 2] = int(px[i + 2] * ia + b * a + 0.5)


def ellipse(cx, cy, rx, ry, color, alpha=1.0, soft=2.0):
    r, g, b = color
    x0, x1 = int(cx - rx - 2), int(cx + rx + 2)
    y0, y1 = int(cy - ry - 2), int(cy + ry + 2)
    edge = soft / max(1.0, min(rx, ry))
    for y in range(y0, y1 + 1):
        ny = (y - cy) / ry
        for x in range(x0, x1 + 1):
            nx = (x - cx) / rx
            d = math.sqrt(nx * nx + ny * ny)
            cov = clamp((1.0 - d) / edge * 0.5 + 0.5) * alpha
            if cov > 0.0:
                put(x, y, r, g, b, cov)


def capsule(x1, y1, x2, y2, rad, color, alpha=1.0, soft=2.0):
    r, g, b = color
    dx, dy = x2 - x1, y2 - y1
    length2 = dx * dx + dy * dy
    x0 = int(min(x1, x2) - rad - 2)
    x1b = int(max(x1, x2) + rad + 2)
    y0 = int(min(y1, y2) - rad - 2)
    y1b = int(max(y1, y2) + rad + 2)
    for y in range(y0, y1b + 1):
        for x in range(x0, x1b + 1):
            if length2 == 0:
                t = 0.0
            else:
                t = clamp(((x - x1) * dx + (y - y1) * dy) / length2)
            qx, qy = x1 + t * dx, y1 + t * dy
            d = math.hypot(x - qx, y - qy)
            cov = clamp((rad - d) / soft * 0.5 + 0.5) * alpha
            if cov > 0.0:
                put(x, y, r, g, b, cov)


def rrect(cx, cy, w, h, rad, color, alpha=1.0, soft=2.0):
    r, g, b = color
    hw, hh = w / 2.0, h / 2.0
    for y in range(int(cy - hh - 2), int(cy + hh + 3)):
        for x in range(int(cx - hw - 2), int(cx + hw + 3)):
            qx = abs(x - cx) - (hw - rad)
            qy = abs(y - cy) - (hh - rad)
            d = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - rad
            cov = clamp(-d / soft * 0.5 + 0.5) * alpha
            if cov > 0.0:
                put(x, y, r, g, b, cov)


def radial_light(cx, cy, rad, color, strength):
    """Warm glow: brightens pixels toward `color` with a soft falloff."""
    cr, cg, cb = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0
    x0, x1 = int(cx - rad), int(cx + rad)
    y0, y1 = int(cy - rad), int(cy + rad)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if x < 0 or x >= W or y < 0 or y >= H:
                continue
            d = math.hypot(x - cx, y - cy) / rad
            if d >= 1.0:
                continue
            f = (1.0 - d) * (1.0 - d) * strength
            i = (y * W + x) * 3
            px[i] = int(px[i] + (255 - px[i]) * f * cr + 0.5)
            px[i + 1] = int(px[i + 1] + (255 - px[i + 1]) * f * cg + 0.5)
            px[i + 2] = int(px[i + 2] + (255 - px[i + 2]) * f * cb + 0.5)


# ---------------------------------------------------------------- backdrop

def backdrop():
    top = (238, 234, 228)
    mid = (216, 211, 203)
    bot = (183, 177, 169)
    for y in range(H):
        if y < 700:
            t = y / 700.0
            c = tuple(int(top[i] + (mid[i] - top[i]) * t + 0.5) for i in range(3))
        else:
            t = (y - 700) / (H - 700.0)
            c = tuple(int(mid[i] + (bot[i] - mid[i]) * t + 0.5) for i in range(3))
        row = bytes(c) * W
        px[y * W * 3:(y + 1) * W * 3] = row
    # studio sweep: soft pool of light behind the product
    radial_light(512, 500, 520, (255, 252, 244), 0.16)
    # floor sheen just in front of the product
    ellipse(512, 742, 300, 30, (255, 255, 255), alpha=0.10, soft=14.0)


# ---------------------------------------------------------------- the base

BCX, BCY = 512, 648          # centre of the base top plate
BRX, BRY = 305, 86           # radii of the top plate
BODY = 44                    # cylinder height


def metal_top():
    """Brushed-metal top plate with radial shading and streak noise."""
    cx, cy, rx, ry = BCX, BCY, BRX, BRY
    edge = 2.0 / ry
    for y in range(int(cy - ry - 2), int(cy + ry + 3)):
        ny = (y - cy) / ry
        for x in range(int(cx - rx - 2), int(cx + rx + 3)):
            nx = (x - cx) / rx
            d = math.sqrt(nx * nx + ny * ny)
            cov = clamp((1.0 - d) / edge * 0.5 + 0.5)
            if cov <= 0.0:
                continue
            hl = clamp((-nx - ny) * 0.5 + 0.5)          # light from top-left
            shade = 0.86 + 0.20 * hl - 0.16 * d * d
            streak = ((x * 31 + y * 101) % 7) - 3       # brushed streaks
            base = 178 + streak
            put(x, y, int(base * shade), int(base * shade * 0.99),
                int(base * shade * 0.96), cov)


def base():
    # soft contact shadow
    ellipse(BCX, BCY + BODY + 26, 345, 42, (40, 36, 32), alpha=0.34, soft=16.0)
    ellipse(BCX, BCY + BODY + 18, 250, 26, (40, 36, 32), alpha=0.28, soft=10.0)
    # cylinder body: vertical wall with soft edges, then the curved
    # underside, shaded darker toward the sides so the puck reads round
    for y in range(BCY, BCY + BODY + BRY + 2):
        if y <= BCY + BODY:
            t = (y - BCY) / BODY
            shade = 142 - 38 * t
            for x in range(BCX - BRX - 2, BCX + BRX + 3):
                fx = abs(x - BCX) / BRX
                cov = clamp((BRX - abs(x - BCX)) / 2.0 * 0.5 + 0.5)
                if cov <= 0.0:
                    continue
                s = shade * (1.0 - 0.22 * fx * fx)
                put(x, y, int(s), int(s * 0.99), int(s * 0.96), cov)
        else:
            ny = (y - (BCY + BODY)) / BRY
            shade = 104 - 14 * ny
            for x in range(BCX - BRX - 2, BCX + BRX + 3):
                nx = (x - BCX) / BRX
                d = math.sqrt(nx * nx + ny * ny)
                cov = clamp((1.0 - d) / (2.0 / BRY) * 0.5 + 0.5)
                if cov <= 0.0:
                    continue
                s = shade * (1.0 - 0.22 * nx * nx)
                put(x, y, int(s), int(s * 0.99), int(s * 0.96), cov)
    # warm light the flame throws onto the front of the body
    ellipse(BCX, BCY + 26, 190, 30, (255, 150, 60), alpha=0.13, soft=12.0)
    metal_top()
    # bevel highlight on the rim
    ellipse(BCX, BCY - 3, BRX - 6, BRY - 5, (226, 224, 218), alpha=0.35, soft=3.0)
    metal_top_center()


def metal_top_center():
    """Re-lay the inner plate so the bevel reads as a thin rim line only."""
    ellipse(BCX, BCY, BRX - 14, BRY - 10, (186, 184, 179), alpha=0.55, soft=3.0)


def screw(x, y):
    ellipse(x, y, 8, 8, (104, 102, 99))
    ellipse(x - 1, y - 1, 5, 5, (158, 155, 150))
    capsule(x - 4, y, x + 4, y, 1.3, (70, 68, 66))


# tiny 5x7 bitmap font for the printed product label
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '·': ("00000", "00000", "00000", "00110", "00110", "00000", "00000"),
    ' ': ("00000",) * 7,
}


def draw_text(cx, cy, text, scale, color):
    adv = 6 * scale
    width = adv * len(text) - scale
    x = cx - width // 2
    y0 = cy - (7 * scale) // 2
    for ch in text:
        glyph = FONT[ch]
        for gy, rowbits in enumerate(glyph):
            for gx, bit in enumerate(rowbits):
                if bit == '1':
                    for yy in range(y0 + gy * scale, y0 + (gy + 1) * scale):
                        for xx in range(x + gx * scale, x + (gx + 1) * scale):
                            put(xx, yy, color[0], color[1], color[2], 1.0)
        x += adv


def fittings():
    # screws near the rim of the top plate
    for sx, sy in ((276, 616), (748, 616), (332, 700), (692, 700)):
        screw(sx, sy)
    # printed label, silkscreened straight onto the curved front of
    # the puck: no plate behind it, just light lettering on the metal,
    # so the body's own shading runs uninterrupted behind the words
    draw_text(BCX, 686, "EMBER-1 · USB CAMPFIRE", 3, (219, 213, 201))
    # power switch, front right
    rrect(762, 684, 44, 24, 6, (44, 43, 44))
    rrect(754, 684, 18, 16, 4, (196, 193, 187))
    # LED, front left: halo then bright core
    ellipse(258, 686, 13, 13, (90, 230, 120), alpha=0.30, soft=5.0)
    ellipse(258, 686, 5, 5, (120, 255, 150))
    ellipse(257, 685, 2, 2, (230, 255, 235))


# ---------------------------------------------------------------- fire

RING_CX, RING_CY, RING_RX, RING_RY = 512, 612, 168, 52


def stone(x, y, rx, ry, tone):
    ellipse(x, y + 3, rx, ry, (tone - 46, tone - 46, tone - 44), alpha=0.45, soft=4.0)
    ellipse(x, y, rx, ry, (tone, tone, tone - 3))
    ellipse(x - rx * 0.28, y - ry * 0.34, rx * 0.5, ry * 0.42,
            (tone + 34, tone + 34, tone + 30), alpha=0.5, soft=3.0)


def stones(back):
    rng = random.Random(SEED + (1 if back else 2))
    n = 11
    for i in range(n):
        a = 2 * math.pi * i / n + 0.14
        x = RING_CX + RING_RX * math.cos(a)
        y = RING_CY + RING_RY * math.sin(a)
        if back and y > RING_CY:
            continue
        if not back and y <= RING_CY:
            continue
        tone = 118 + rng.randint(-16, 20)
        stone(x, y, 27 + rng.randint(-4, 5), 19 + rng.randint(-3, 4), tone)


def log(x1, y1, x2, y2, rad):
    capsule(x1, y1 + 4, x2, y2 + 4, rad, (40, 24, 14), alpha=0.35, soft=4.0)
    capsule(x1, y1, x2, y2, rad, (110, 72, 42))
    capsule(x1, y1 - rad * 0.34, x2, y2 - rad * 0.34, rad * 0.52, (146, 99, 60), alpha=0.8)
    # cut end with growth rings
    ellipse(x2, y2, rad * 0.92, rad * 0.92, (203, 158, 104))
    ellipse(x2, y2, rad * 0.58, rad * 0.58, (178, 128, 76))
    ellipse(x2, y2, rad * 0.26, rad * 0.26, (203, 158, 104))


def flame(cx, base_y, h, w, color, sway, alpha, phase=0.0):
    top = base_y - h
    for y in range(int(top), int(base_y) + 1):
        t = (base_y - y) / h                       # 0 bottom, 1 tip
        halfw = w * (math.sin(math.pi * min(t * 1.12, 1.0)) ** 0.72) * (1.0 - 0.22 * t)
        if halfw < 0.6:
            continue
        # organic flicker: the two edges breathe independently, a small
        # tongue of flame licks out on the side the flame leans toward,
        # and the tip pinches irregularly instead of closing smoothly
        hl = halfw * (1.0 + 0.16 * math.sin(t * 5.3 + phase))
        hr = halfw * (1.0 - 0.13 * math.sin(t * 4.1 + phase * 1.7))
        hr += math.exp(-((t - 0.52) ** 2) / 0.004) * w * 0.30
        pinch = 1.0 - 0.18 * t * (0.5 + 0.5 * math.sin(t * 9.0 + phase * 2.3))
        hl *= pinch
        hr *= pinch
        cxc = cx + sway * t * t + 3.0 * math.sin(t * 3.0 + phase)
        for x in range(int(cxc - hl - 2), int(cxc + hr + 3)):
            d = (x - cxc) / hl if x < cxc else (x - cxc) / hr
            cov = clamp((1.0 - abs(d)) * halfw / 2.0) * alpha
            if cov > 0.0:
                put(x, y, color[0], color[1], color[2], cov)


def fire():
    stones(back=True)
    log(428, 630, 566, 594, 17)
    log(596, 630, 458, 594, 17)
    log(474, 642, 556, 610, 14)
    # the flame lights everything around it
    radial_light(512, 545, 330, (255, 166, 74), 0.30)
    radial_light(512, 560, 170, (255, 190, 96), 0.38)
    # soft halo hugging the fire bed, so the logs and stones glow
    ellipse(512, 608, 158, 36, (255, 138, 38), alpha=0.15, soft=10.0)
    ellipse(512, 602, 104, 24, (255, 176, 64), alpha=0.18, soft=8.0)
    # living flame, layered flickering tongues
    flame(512, 616, 196, 62, (255, 106, 18), 12, 0.95, phase=0.0)
    flame(512, 616, 158, 45, (255, 158, 26), 9, 0.97, phase=1.3)
    flame(512, 616, 116, 30, (255, 205, 62), 6, 0.98, phase=2.1)
    flame(512, 616, 74, 16, (255, 242, 186), 3, 1.0, phase=2.9)
    # warm reflection of the fire on the floor in front
    ellipse(512, 736, 130, 13, (255, 140, 50), alpha=0.10, soft=8.0)
    stones(back=False)
    # a last breath of halo over the front stones
    ellipse(512, 616, 172, 40, (255, 150, 50), alpha=0.07, soft=12.0)


# ---------------------------------------------------------------- cable & accessory

def cable():
    # cubic Bezier trailing off the left edge of the frame
    p0, p1, p2, p3 = (232, 632), (120, 648), (84, 748), (-16, 792)
    pts = []
    for i in range(61):
        t = i / 60.0
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    for x, y in pts:
        ellipse(x, y + 5, 12, 12, (30, 28, 28), alpha=0.20, soft=5.0)
    for x, y in pts:
        ellipse(x, y, 11, 11, (26, 26, 29))
    for x, y in pts[::2]:
        ellipse(x - 3, y - 4, 4.5, 4.5, (86, 86, 92), alpha=0.55, soft=2.0)
    # connector housing where the cable meets the base
    rrect(232, 632, 60, 30, 8, (38, 38, 42))
    rrect(224, 632, 16, 20, 4, (120, 120, 126))


def marshmallow():
    # the one accessory: a plump marshmallow pierced on the END of a
    # stick, hovering just above the flame's edge to toast.  The stick
    # and the marshmallow share one axis, so it sits on the stick's end
    # instead of floating beside it.
    ex, ey = 638, 406            # far end, where the stick enters
    nx, ny = 604, 428            # near end, toward the flame
    capsule(816, 302, 630, 410, 4.5, (158, 126, 84))
    capsule(810, 306, 636, 408, 1.8, (198, 166, 118), alpha=0.8)
    # soft shadow side, low and away from the firelight
    capsule(ex + 6, ey + 9, nx + 6, ny + 9, 30, (214, 202, 184), alpha=0.55, soft=3.0)
    # plump body: short axis, fat radius
    capsule(ex, ey, nx, ny, 30, (246, 241, 233))
    capsule(ex - 4, ey - 5, nx - 4, ny - 5, 21, (253, 250, 245), alpha=0.8)
    # firelight warming the side that faces the flame
    radial_light(596, 436, 95, (255, 172, 84), 0.16)
    # golden toasted patch on the flame-facing end
    ellipse(594, 440, 19, 14, (204, 140, 60), alpha=0.60, soft=5.0)
    ellipse(590, 445, 11, 8, (164, 98, 34), alpha=0.55, soft=4.0)
    ellipse(600, 430, 7, 5, (226, 170, 92), alpha=0.50, soft=3.0)


# ---------------------------------------------------------------- finish

def finish():
    rng = random.Random(SEED)
    noise = [[rng.randint(-3, 3) for _ in range(W // 2)] for _ in range(H // 2)]
    for y in range(H):
        nrow = noise[y // 2]
        cy = (y - 512) / 660.0
        for x in range(W):
            cx = (x - 512) / 660.0
            d2 = cx * cx + cy * cy
            vig = 1.0 - 0.17 * clamp(d2 - 0.30, 0.0, 1.0)
            n = nrow[x // 2]
            i = (y * W + x) * 3
            for k in range(3):
                v = int(px[i + k] * vig + n + 0.5)
                px[i + k] = (0 if v < 0 else 255 if v > 255 else v) & ~1


def write_png(path):
    raw = bytearray()
    stride = W * 3
    prev = bytes(stride)
    for y in range(H):
        row = bytes(px[y * stride:(y + 1) * stride])
        filt = bytearray(stride)
        for i in range(stride):
            filt[i] = (row[i] - prev[i]) & 0xFF if i >= 3 else row[i]
            # Sub filter uses the left neighbour in the same row
            filt[i] = (row[i] - (row[i - 3] if i >= 3 else 0)) & 0xFF
        raw.append(1)
        raw.extend(filt)
        prev = row
    data = zlib.compress(bytes(raw), 6)

    def chunk(tag, payload):
        c = struct.pack(">I", len(payload)) + tag + payload
        return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", data)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    backdrop()
    cable()
    base()
    fittings()
    fire()
    marshmallow()
    finish()
    os.makedirs("/output", exist_ok=True)
    write_png("/output/entry.png")


if __name__ == "__main__":
    main()
