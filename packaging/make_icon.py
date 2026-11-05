#!/usr/bin/env python3
"""Generate the Finish 3D icon: an isometric 3D IC chip with gold pins.

Renders at 8x supersample and downscales for clean edges. Writes a 64x64 PNG
(the KiCad PCM / toolbar size) plus a 256x256 for other uses.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

SS = 8  # supersample factor


def _lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def draw_icon(size: int) -> Image.Image:
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx = W * 0.5
    cy = W * 0.40          # top-face centre
    a = W * 0.30           # half-width of the rhombus (x)
    b = a * 0.5            # half-height of the rhombus (y)  -> 2:1 iso
    h = W * 0.26           # body height (extrusion)

    # top face corners
    v_top = (cx, cy - b)
    v_right = (cx + a, cy)
    v_bot = (cx, cy + b)
    v_left = (cx - a, cy)

    def down(p):
        return (p[0], p[1] + h)

    # colours (dark IC body, gold leads)
    TOP = (58, 64, 76, 255)
    LEFT = (34, 38, 46, 255)
    RIGHT = (22, 25, 31, 255)
    EDGE = (90, 100, 118, 255)
    GOLD = (226, 170, 70, 255)
    GOLD_HI = (245, 206, 120, 255)

    # ---- body faces ----
    # left-front face
    d.polygon([v_left, v_bot, down(v_bot), down(v_left)], fill=LEFT)
    # right-front face
    d.polygon([v_bot, v_right, down(v_right), down(v_bot)], fill=RIGHT)
    # top face
    d.polygon([v_top, v_right, v_bot, v_left], fill=TOP)

    # subtle top highlight edges
    d.line([v_left, v_top, v_right], fill=EDGE, width=max(1, SS))
    d.line([v_left, v_bot], fill=(70, 78, 92, 255), width=max(1, SS))
    d.line([v_right, v_bot], fill=(70, 78, 92, 255), width=max(1, SS))
    # vertical front edge
    d.line([v_bot, down(v_bot)], fill=(14, 16, 20, 255), width=max(1, SS))

    # ---- gold gull-wing leads along the two front-bottom edges ----
    n = 4
    drop = W * 0.085        # vertical knee drop
    foot_x = W * 0.075      # horizontal foot reach
    foot_dy = W * 0.030     # foot follows the iso ground slightly
    widthf = 0.56           # fraction of each segment the lead occupies

    def leads(edge_a, edge_b, out_sign):
        for i in range(n):
            t0 = (i + 0.5) / n
            half = widthf * 0.5 / n
            p1 = _lerp(edge_a, edge_b, max(0.0, t0 - half))
            p2 = _lerp(edge_a, edge_b, min(1.0, t0 + half))
            # knee: straight down the body side
            k1 = (p1[0], p1[1] + drop)
            k2 = (p2[0], p2[1] + drop)
            # foot: out to the side, tracking the iso ground plane
            f1 = (k1[0] + out_sign * foot_x, k1[1] + foot_dy)
            f2 = (k2[0] + out_sign * foot_x, k2[1] + foot_dy)
            # vertical part of the lead
            d.polygon([p1, p2, k2, k1], fill=GOLD)
            # foot
            d.polygon([k1, k2, f2, f1], fill=GOLD_HI)
            d.line([p1, k1, f1], fill=GOLD_HI, width=max(1, SS))

    # left face bottom edge: down(v_bot) -> down(v_left), feet reach left
    leads(down(v_bot), down(v_left), out_sign=-1)
    # right face bottom edge: down(v_bot) -> down(v_right), feet reach right
    leads(down(v_bot), down(v_right), out_sign=+1)

    # ---- pin-1 dot on the top face (teal) ----
    dot_c = _lerp(_lerp(v_left, v_top, 0.30), v_bot, 0.18)
    r = W * 0.035
    d.ellipse([dot_c[0] - r, dot_c[1] - r, dot_c[0] + r, dot_c[1] + r],
              fill=(90, 210, 200, 255))

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
