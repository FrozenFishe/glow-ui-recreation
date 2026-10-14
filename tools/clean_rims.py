"""Clean the hero photo slice under the edges of the shapes drawn on top of it.

The hero slice is the original's pixels, so it already contains the phone UI and the badge. The rebuilds draw
those shapes again on top (screen, tab bar, island, search field, tiles, cards, Book buttons, home indicator,
badge). Inside a shape that's harmless, because the drawn fill is opaque, but along the edge the tool's
anti-aliased edge blends over the photo's own anti-aliased edge, so every edge gets anti-aliased twice.

This replaces a band around each drawn outline (from 2px inside to 2px outside) with the colour just outside
the shape: each band pixel takes the slice's colour 3px out along the outline's normal. The rebuild's own edge
then blends over clean background, as it does for shapes on the backdrop plate. Shapes are processed in
drawing order, so a nested shape (a Book button in a card) samples its parent's interior.

usage: clean_rims.py <hero_slice.png> <out.png> [--shapes tools/glow_shapes_tuned.json] [--x0 712 --y0 0]
"""
import argparse
import json

import numpy as np
from PIL import Image

INNER, OUTER, SAMPLE = 2.0, 2.0, 3.0

# drawn over the hero, bottom to top (names from glow_shapes_tuned.json, plus the phone screen and tab bar paths)
# The phone screen and the trusted badge are left out on purpose: their edges in the photo are physical (a glass
# highlight along the top of the screen only, the badge's shaded rim over the photo), which a flat outline + fill
# can't reproduce, so there the photo's own edge under the drawn shape is closer than any redrawn edge (measured:
# cleaning them took the website from 0.026% to 0.05%+, cleaning the small shapes alone took those to 0 px).
ORDER = ["island", "app_search", "app_filter", "tile_1", "tile_2", "tile_3", "tile_4", "tile_5",
         "card_1", "card_2", "book_1", "book_2", "home_indicator"]
FIXED = {"screen": ([1083, 188, 299, 673], (42, 42, 44, 44)),        # make_kit.py: top r42, bottom follows the bezel (44)
         "tab_bar_strip": ([1083, 791, 299, 70], (0, 0, 44, 44))}


def sd_rrect(px, py, box, radii):
    """Signed distance to a rectangle with per-corner radii (tl, tr, br, bl); positive outside."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx, dy = px - cx, py - cy
    tl, tr, br, bl = radii
    r = np.where(dx < 0, np.where(dy < 0, tl, bl), np.where(dy < 0, tr, br))
    qx, qy = np.abs(dx) - (w / 2 - r), np.abs(dy) - (h / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def bilinear(img, x, y):
    H, W = img.shape[:2]
    x = np.clip(x, 0, W - 1.001); y = np.clip(y, 0, H - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    a, b, c, d = img[y0, x0], img[y0, x0 + 1], img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def clean(img, shapes, x0=712.0, y0=0.0, order=ORDER, fixed=FIXED):
    """Return a copy of img (float RGB, a slice whose top-left is at x0,y0 in design px) with the rims cleaned."""
    img = img.copy()
    H, W = img.shape[:2]
    shapes = {s["name"]: s for s in shapes}
    yy, xx = np.mgrid[0:H, 0:W]
    px, py = xx + 0.5 + x0, yy + 0.5 + y0  # pixel centres in design coordinates
    total = 0
    for n in order:
        if n in fixed:
            box, radii = fixed[n]
        elif n in shapes:
            s = shapes[n]
            box = s["box"]
            r = s.get("r", 0) if s["kind"] == "rect" else box[2] / 2
            radii = (r, r, r, r)
        else:
            continue
        sd = sd_rrect(px, py, box, radii)
        band = (sd > -INNER) & (sd < OUTER)
        if not band.any():
            continue
        e = 0.25  # outward normal from the distance field's gradient
        gx = sd_rrect(px + e, py, box, radii) - sd_rrect(px - e, py, box, radii)
        gy = sd_rrect(px, py + e, box, radii) - sd_rrect(px, py - e, box, radii)
        g = np.hypot(gx, gy) + 1e-9
        step = SAMPLE - sd
        img[band] = bilinear(img, (xx + gx / g * step)[band], (yy + gy / g * step)[band])
        total += int(band.sum())
    return img, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hero")
    ap.add_argument("out")
    ap.add_argument("--shapes", default="tools/glow_shapes_tuned.json")
    ap.add_argument("--x0", type=float, default=712)
    ap.add_argument("--y0", type=float, default=0)
    a = ap.parse_args()
    img = np.asarray(Image.open(a.hero).convert("RGB"), dtype=np.float64)
    out, total = clean(img, json.load(open(a.shapes)), a.x0, a.y0)
    Image.fromarray(np.clip(np.round(out), 0, 255).astype(np.uint8)).save(a.out)
    print(f"cleaned {total} rim pixels -> {a.out}")

if __name__ == "__main__":
    main()


def paint_parents(under, ss=8):
    """Paint the phone screen and tab bar (the parents every phone shape sits on) onto a full-canvas float RGB image,
    as make_kit.py draws them. tune_shapes.py --under uses the result as the real background of the nested shapes."""
    from PIL import ImageDraw
    H, W = under.shape[:2]
    x0, y0, x1, y1 = 1070, 180, 1395, 870
    out = under.copy()
    for (bx, by, bw, bh), (tl, tr, br, bl), col in [(FIXED["screen"][0], FIXED["screen"][1], (247, 247, 247)),
                                                    (FIXED["tab_bar_strip"][0], FIXED["tab_bar_strip"][1], (254, 254, 254))]:
        m = Image.new("L", ((x1 - x0) * ss, (y1 - y0) * ss), 0)
        d = ImageDraw.Draw(m)
        X0, Y0, X1, Y1 = (bx - x0) * ss, (by - y0) * ss, (bx + bw - x0) * ss, (by + bh - y0) * ss
        mid = (Y0 + Y1) / 2
        # top half with the top radii, bottom half with the bottom radii
        d.rounded_rectangle([X0, Y0, X1, mid + max(tl, tr) * ss], radius=max(tl, tr) * ss, fill=255) if max(tl, tr) else d.rectangle([X0, Y0, X1, mid], fill=255)
        d.rounded_rectangle([X0, mid - max(bl, br) * ss, X1, Y1], radius=max(bl, br) * ss, fill=255) if max(bl, br) else d.rectangle([X0, mid, X1, Y1], fill=255)
        a = (np.asarray(m, np.float64) / 255).reshape(y1 - y0, ss, x1 - x0, ss).mean(axis=(1, 3))[..., None]
        out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - a) + np.array(col, float) * a
    return out
