#!/usr/bin/env python3
"""EMBER-1 - the USB campfire. A studio catalogue photo of an impossible gadget.

Pure standard library. Deterministic. Writes /output/entry.png (1024x1024).
"""
import math
import os
import struct
import zlib
import binascii

W = H = 1024
PX = bytearray(W * H * 3)


def set_px(x, y, r, g, b):
    i = (y * W + x) * 3
    PX[i] = r
    PX[i + 1] = g
    PX[i + 2] = b


def blend(x, y, col, a):
    if a <= 0.0:
        return
    if a >= 1.0:
        set_px(x, y, col[0], col[1], col[2])
        return
    i = (y * W + x) * 3
    ia = 1.0 - a
    PX[i] = int(PX[i] * ia + col[0] * a + 0.5)
    PX[i + 1] = int(PX[i + 1] * ia + col[1] * a + 0.5)
    PX[i + 2] = int(PX[i + 2] * ia + col[2] * a + 0.5)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ---------------------------------------------------------------- shapes
def ellipse(cx, cy, rx, ry, col, alpha=1.0, feather=0.06):
    """Soft-edged filled ellipse, drawn only inside its bounding box."""
    x0 = max(0, int(cx - rx - 2))
    x1 = min(W - 1, int(cx + rx + 2))
    y0 = max(0, int(cy - ry - 2))
    y1 = min(H - 1, int(cy + ry + 2))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            d = math.sqrt(dx * dx + dy * dy)
            if d < 1.0 + feather:
                a = alpha * clamp((1.0 + feather - d) / (2.0 * feather), 0.0, 1.0)
                blend(x, y, col, a)


def capsule(xa, ya, xb, yb, rad, col, alpha=1.0):
    """Thick line segment with round caps (soft edge)."""
    x0 = max(0, int(min(xa, xb) - rad - 2))
    x1 = min(W - 1, int(max(xa, xb) + rad + 2))
    y0 = max(0, int(min(ya, yb) - rad - 2))
    y1 = min(H - 1, int(max(ya, yb) + rad + 2))
    vx, vy = xb - xa, yb - ya
    vv = vx * vx + vy * vy or 1.0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            t = clamp(((x - xa) * vx + (y - ya) * vy) / vv, 0.0, 1.0)
            px, py = xa + t * vx, ya + t * vy
            d = math.hypot(x - px, y - py)
            if d < rad + 1.5:
                a = alpha * clamp((rad + 1.5 - d) / 3.0, 0.0, 1.0)
                blend(x, y, col, a)


def rrect(cx, cy, w, h, rad, col, alpha=1.0):
    """Soft rounded rectangle centred at (cx, cy)."""
    x0 = max(0, int(cx - w / 2 - 2))
    x1 = min(W - 1, int(cx + w / 2 + 2))
    y0 = max(0, int(cy - h / 2 - 2))
    y1 = min(H - 1, int(cy + h / 2 + 2))
    hw, hh = w / 2.0, h / 2.0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            qx = abs(x - cx) - (hw - rad)
            qy = abs(y - cy) - (hh - rad)
            d = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - rad
            if d < 1.5:
                blend(x, y, col, alpha * clamp((1.5 - d) / 3.0, 0.0, 1.0))


def glow(cx, cy, rx, ry, col, a0):
    """Warm radial light falloff."""
    x0 = max(0, int(cx - rx))
    x1 = min(W - 1, int(cx + rx))
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x - cx) / rx
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                f = 1.0 - math.sqrt(d2)
                blend(x, y, col, a0 * f * f)


def teardrop(cx, base_y, height, max_w, lean, col, alpha):
    """Flame tongue: wide at the base, pointed tip leaning to one side."""
    tip_y = base_y - height
    x0 = max(0, int(cx - max_w - abs(lean) - 3))
    x1 = min(W - 1, int(cx + max_w + abs(lean) + 3))
    y0 = max(0, int(tip_y - 2))
    y1 = min(H - 1, int(base_y + 2))
    for y in range(y0, y1 + 1):
        t = (base_y - y) / height  # 0 at base, 1 at tip
        if t < 0.0 or t > 1.0:
            continue
        cen = cx + lean * t * t
        hw = max_w * (math.sin(math.pi * min(t * 1.12, 1.0)) ** 0.75) * (1.0 - 0.22 * t)
        if hw < 0.6:
            continue
        for x in range(x0, x1 + 1):
            d = abs(x - cen)
            if d < hw + 2.0:
                blend(x, y, col, alpha * clamp((hw + 2.0 - d) / 4.0, 0.0, 1.0))


# ---------------------------------------------------------------- 5x7 font
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
    '·': ("00000", "00000", "00000", "00100", "00000", "00000", "00000"),
    ' ': ("00000",) * 7,
}


def draw_text(cx, y, text, scale, col, alpha):
    adv = 5 * scale + scale
    total = adv * len(text) - scale
    x = int(cx - total / 2)
    for ch in text:
        glyph = FONT[ch]
        for row in range(7):
            bits = glyph[row]
            for col_i in range(5):
                if bits[col_i] == '1':
                    for yy in range(y + row * scale, y + (row + 1) * scale):
                        for xx in range(x + col_i * scale, x + (col_i + 1) * scale):
                            if 0 <= xx < W and 0 <= yy < H:
                                blend(xx, yy, col, alpha)
        x += adv


# ---------------------------------------------------------------- backdrop
def backdrop():
    top = (233, 227, 219)
    bot = (193, 185, 175)
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        row = bytes((r, g, b)) * W
        PX[y * W * 3:(y + 1) * W * 3] = row


# ---------------------------------------------------------------- scene
def scene():
    backdrop()

    # floor sheen + contact shadow
    ellipse(512, 772, 350, 34, (255, 252, 244), 0.10, 0.5)
    ellipse(512, 748, 305, 44, (58, 50, 44), 0.34, 0.45)

    # ambient warmth behind the product
    glow(512, 545, 300, 235, (255, 176, 92), 0.20)

    # ---- USB cable, trailing off the left edge
    pts = [(272, 690), (204, 708), (132, 744), (62, 784), (-12, 828)]
    for i in range(len(pts) - 1):
        capsule(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], 10, (26, 26, 29), 1.0)
    for i in range(len(pts) - 1):
        capsule(pts[i][0], pts[i][1] - 3, pts[i + 1][0], pts[i + 1][1] - 3, 3, (86, 86, 92), 0.45)

    # ---- base puck: cylindrical side with vertical shading
    for y in range(636, 752):
        t = (y - 636) / 116.0
        shade = 1.0 - 0.38 * t
        col = (int(168 * shade), int(172 * shade), int(178 * shade))
        capsule(268, y, 756, y, 1, col, 1.0)
    rrect(512, 748, 496, 14, 7, (96, 98, 104), 0.55)  # bottom rim shadow line
    # top face
    ellipse(512, 640, 250, 54, (196, 200, 206), 1.0, 0.03)
    ellipse(512, 636, 238, 48, (208, 212, 218), 0.85, 0.05)
    # rim screws
    for sx, sy in [(300, 632), (724, 632), (356, 656), (668, 656)]:
        ellipse(sx, sy, 7, 5, (120, 124, 130), 1.0, 0.25)
        ellipse(sx - 1, sy - 1, 3, 2, (226, 230, 236), 0.9, 0.3)
    # plug housing where the cable meets the base
    rrect(258, 688, 40, 24, 6, (44, 44, 48), 1.0)
    rrect(238, 688, 12, 14, 3, (150, 154, 160), 1.0)

    # silkscreen lettering on the front of the puck
    draw_text(512, 684, "EMBER-1 · USB CAMPFIRE", 3, (240, 238, 230), 0.92)
    # LED + power switch
    glow(352, 728, 16, 12, (90, 255, 140), 0.5)
    ellipse(352, 728, 6, 5, (64, 230, 120), 1.0, 0.3)
    rrect(648, 726, 34, 13, 6, (70, 72, 78), 1.0)
    rrect(656, 726, 12, 8, 4, (210, 214, 220), 0.9)

    # ---- ring of stones
    stones = [(-148, 6), (-108, 20), (-58, 28), (0, 31), (58, 28), (108, 20),
              (148, 6), (-128, -8), (128, -8), (-78, -16), (78, -16), (0, -20)]
    for i, (dx, dy) in enumerate(stones):
        g = 118 + (i * 13) % 34
        ellipse(512 + dx, 622 + dy, 30, 19, (g, g, g + 4), 1.0, 0.10)
        ellipse(512 + dx - 3, 622 + dy - 5, 20, 11, (g + 34, g + 34, g + 36), 0.55, 0.25)

    # ---- three crossed logs
    log_col = (122, 82, 50)
    log_hi = (150, 108, 68)
    capsule(418, 618, 592, 584, 17, log_col, 1.0)
    capsule(428, 586, 602, 620, 17, (110, 74, 45), 1.0)
    capsule(472, 630, 556, 576, 15, log_col, 1.0)
    capsule(424, 610, 586, 580, 5, log_hi, 0.35)
    capsule(436, 580, 594, 612, 5, log_hi, 0.30)

    def log_end(cx, cy, r):
        ellipse(cx, cy, r, r * 0.82, (206, 170, 124), 1.0, 0.08)
        for rr, cc in [(0.72, (188, 148, 102)), (0.5, (206, 170, 124)), (0.3, (182, 140, 96))]:
            ellipse(cx, cy, r * rr, r * rr * 0.82, cc, 0.8, 0.2)
        ellipse(cx, cy, r * 0.12, r * 0.1, (150, 112, 70), 0.9, 0.3)

    log_end(418, 618, 17)
    log_end(602, 620, 16)
    log_end(556, 576, 14)

    # warm spill over logs and stones
    glow(512, 585, 190, 95, (255, 166, 74), 0.28)

    # ---- the flame (slightly asymmetric, leaning right)
    teardrop(512, 616, 196, 56, 14, (255, 110, 16), 0.88)
    teardrop(510, 612, 158, 42, 12, (255, 168, 34), 0.92)
    teardrop(512, 606, 116, 28, 9, (255, 216, 110), 0.95)
    teardrop(513, 598, 74, 15, 6, (255, 246, 214), 0.98)
    # a small side lick of flame
    teardrop(478, 610, 96, 20, -16, (255, 132, 24), 0.75)
    teardrop(514, 592, 46, 8, 4, (255, 252, 232), 0.95)  # bright heart of the flame
    glow(512, 520, 150, 130, (255, 190, 96), 0.30)

    # ---- THE accessory: one marshmallow on a stick, toasting
    capsule(574, 466, 664, 388, 4, (146, 110, 70), 1.0)   # the stick
    capsule(574, 466, 664, 388, 1, (196, 164, 116), 0.6)
    # marshmallow body
    ellipse(690, 368, 38, 29, (243, 238, 228), 1.0, 0.05)
    ellipse(682, 360, 30, 21, (252, 249, 242), 0.8, 0.15)
    ellipse(690, 382, 34, 16, (226, 218, 204), 0.55, 0.2)  # underside shade
    # golden toasted patch facing the flame
    ellipse(664, 380, 17, 14, (206, 138, 58), 0.85, 0.35)
    ellipse(668, 378, 10, 8, (232, 176, 92), 0.85, 0.35)
    ellipse(660, 384, 5, 4, (168, 102, 40), 0.8, 0.4)


# ---------------------------------------------------------------- finish
def finish():
    # gentle vignette + a whisper of seeded grain in one pass
    state = 123456789
    cx, cy = W / 2.0, H / 2.0
    maxd = math.hypot(cx, cy)
    for y in range(H):
        dy = (y - cy) / maxd
        base = y * W * 3
        for x in range(W):
            dx = (x - cx) / maxd
            d = math.sqrt(dx * dx + dy * dy)
            v = 1.0 - 0.16 * d * d
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            n = ((state >> 16) % 9) - 4
            i = base + x * 3
            PX[i] = clamp(int(PX[i] * v) + n, 0, 255)
            PX[i + 1] = clamp(int(PX[i + 1] * v) + n, 0, 255)
            PX[i + 2] = clamp(int(PX[i + 2] * v) + n, 0, 255)


def write_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        row = PX[y * stride:(y + 1) * stride]
        filt = bytearray(stride)
        for i in range(stride):
            left = row[i - 3] if i >= 3 else 0
            filt[i] = (row[i] - left) & 0xFF
        raw.append(1)  # Sub filter
        raw += filt

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main():
    scene()
    finish()
    os.makedirs("/output", exist_ok=True)
    write_png("/output/entry.png")


if __name__ == "__main__":
    main()
