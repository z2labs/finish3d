#!/usr/bin/env python3
"""Generate the Finish 3D icon: an isometric UV-window EPROM (ceramic DIP).

The classic UV-erasable EPROM: a purple ceramic dual-in-line package with a round
quartz window on top and silver leads down the sides. Rendered isometric at 8x
supersample and downscaled for clean edges. Writes a 64x64 PNG (the KiCad PCM /
toolbar size) plus a 256x256 for docs.
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw

SS = 8  # supersample factor


def _lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def draw_icon(size: int) -> Image.Image:
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- isometric basis (screen displacement per physical unit) ----
    s = W * 0.118
    ex = (s * 1.0, s * 0.5)     # axis 1: down-right (the long DIP axis)
    ey = (s * -1.0, s * 0.5)    # axis 2: down-left (the short axis)
    C = (W * 0.50, W * 0.34)    # centre of the top face

    A = 2.9                     # half-length along axis 1 (long)
    B = 1.85                    # half-length along axis 2 (short)
    H = 1.55                    # body height

    def top(u, v):              # physical top-face coord -> screen
        return (C[0] + u * ex[0] + v * ey[0],
                C[1] + u * ex[1] + v * ey[1])

    def drop(p, z=H):
        return (p[0], p[1] + z * s)

    # top-face corners
    c_back = top(-A, -B)        # upper (min screen-y)
    c_right = top(A, -B)
    c_front = top(A, B)         # lower (max screen-y)
    c_left = top(-A, B)

    # ---- colours: purple ceramic body, silver leads, gold window frame ----
    TOP = (132, 112, 168, 255)
    LEFT = (96, 80, 128, 255)       # long visible side
    RIGHT = (74, 60, 102, 255)      # short visible side
    EDGE = (168, 150, 200, 255)
    DARKEDGE = (40, 32, 56, 255)
    SILVER = (176, 182, 194, 255)
    SILVER_HI = (214, 219, 228, 255)
    GOLD = (214, 176, 92, 255)
    QUARTZ = (190, 214, 226, 255)
    QUARTZ_HI = (236, 246, 250, 255)

    # body faces (painter's order: back faces first)
    d.polygon([c_left, c_front, drop(c_front), drop(c_left)], fill=LEFT)
    d.polygon([c_front, c_right, drop(c_right), drop(c_front)], fill=RIGHT)
    d.polygon([c_back, c_right, c_front, c_left], fill=TOP)

    # top chamfer / edge highlights
    d.line([c_left, c_back, c_right], fill=EDGE, width=max(1, SS))
    d.line([c_left, c_front], fill=EDGE, width=max(1, SS))
    d.line([c_right, c_front], fill=EDGE, width=max(1, SS))
    d.line([c_front, drop(c_front)], fill=DARKEDGE, width=max(1, SS))

    # ---- silver leads along the two visible bottom edges ----
    knee = W * 0.075
    foot_x = W * 0.070
    foot_dy = W * 0.028

    def leads(edge_a, edge_b, out_sign, n, widthf=0.5):
        for i in range(n):
            t0 = (i + 0.5) / n
            half = widthf * 0.5 / n
            p1 = _lerp(edge_a, edge_b, max(0.0, t0 - half))
            p2 = _lerp(edge_a, edge_b, min(1.0, t0 + half))
            k1 = (p1[0], p1[1] + knee)
            k2 = (p2[0], p2[1] + knee)
            f1 = (k1[0] + out_sign * foot_x, k1[1] + foot_dy)
            f2 = (k2[0] + out_sign * foot_x, k2[1] + foot_dy)
            d.polygon([p1, p2, k2, k1], fill=SILVER)
            d.polygon([k1, k2, f2, f1], fill=SILVER_HI)
            d.line([p1, k1, f1], fill=SILVER_HI, width=max(1, SS))

    # DIP: leads on the LONG sides only. In this iso view one long side is
    # visible (front-left) and the short end (front-right) is bare -- like a real
    # dual-in-line package. The second row sits on the hidden back-long side.
    leads(drop(c_front), drop(c_left), out_sign=-1, n=8, widthf=0.55)

    # ---- the quartz UV window on the top face ----
    def circle_on_top(radius, cu=0.0, cv=0.0, steps=64):
        pts = []
        for i in range(steps):
            th = 2 * math.pi * i / steps
            u = cu + radius * math.cos(th)
            v = cv + radius * math.sin(th)
            pts.append(top(u, v))
        return pts

    # gold frame, then quartz, then a highlight crescent
    d.polygon(circle_on_top(1.45), fill=GOLD)
    d.polygon(circle_on_top(1.15), fill=QUARTZ)
    # glassy highlight: a smaller offset disc, lighter
    d.polygon(circle_on_top(0.55, cu=-0.35, cv=-0.30), fill=QUARTZ_HI)
    # window cross-die hint (two faint lines)
    cwin = top(0, 0)
    d.line([top(-1.0, 0), top(1.0, 0)], fill=(150, 176, 190, 150),
           width=max(1, SS // 2))
    d.line([top(0, -1.0), top(0, 1.0)], fill=(150, 176, 190, 150),
           width=max(1, SS // 2))

    # pin-1 notch mark near one end of the top face
    nmark = top(-A + 0.45, 0.0)
    r = W * 0.018
    d.ellipse([nmark[0] - r, nmark[1] - r, nmark[0] + r, nmark[1] + r],
              fill=(230, 232, 238, 255))

    return img.resize((size, size), Image.LANCZOS)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    out64 = draw_icon(64)
    out256 = draw_icon(256)

    targets = [
        os.path.join(repo, "resources", "icon.png"),            # PCM listing
        os.path.join(repo, "finish3d", "icon.png"),             # toolbar button
    ]
    for t in targets:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        out64.save(t)
        print("wrote", t)
    big = os.path.join(repo, "resources", "icon_256.png")
    out256.save(big)
    print("wrote", big)


if __name__ == "__main__":
    main()
