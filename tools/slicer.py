"""Slice small components (icons, logos) out of a design image.

For every region in the spec it tightens the box to the ink, removes the
background into a transparent PNG, traces the ink with potrace into a vector
SVG, and records absolute path data in source pixels so editors (Affinity,
PhotoCraft) and the website can rebuild the component exactly.

usage: slicer.py <source-image> <spec.json> <out-dir>

spec: [{"name": "feat_search", "box": [x, y, w, h]},
       {"name": "logo", "box": [...], "split": true, "min_gap": 30, "threshold": 0.3}]
"threshold" (default 0.5) lowers the ink cut-off so faint, thin strokes survive tracing.
A "split" region is cut into one component per run of ink separated by at
least min_gap empty columns (e.g. a strip of brand logos).
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

UPSCALE = 8          # trace at 8x so small icons keep their curves
INK_THRESHOLD = 0.5  # fraction of full contrast that counts as ink when tracing


def background(rgb):
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.median(border, axis=0)


def inkness(rgb, bg):
    """0..1 per pixel: how far each pixel is from the background colour."""
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    peak = max(np.percentile(dist, 99.5), 30.0)
    return np.clip(dist / peak, 0, 1)


def tight_box(ink, pad=1, cut=0.15):
    ys, xs = np.where(ink > cut)
    if len(xs) == 0:
        return None
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, ink.shape[1])
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, ink.shape[0])
    return x0, y0, x1, y1


def split_columns(ink, min_gap, cut=0.15):
    cols = (ink > cut).any(axis=0)
    runs, start, gap = [], None, 0
    for x, on in enumerate(cols):
        if on:
            if start is None:
                start = x
            gap, end = 0, x
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                runs.append((start, end + 1))
                start, gap = None, 0
    if start is not None:
        runs.append((start, end + 1))
    return runs


TOKEN = re.compile(r"[MmCcLlZz]|-?\d*\.?\d+(?:e-?\d+)?")


def parse_potrace_svg(svg_text):
    """Return subpaths of absolute segments in potrace's output pixel space."""
    height = float(re.search(r'height="([\d.]+)pt"', svg_text).group(1))
    tx, ty = map(float, re.search(r"translate\(([-\d.]+),([-\d.]+)\)", svg_text).group(1, 2))
    sx, sy = map(float, re.search(r"scale\(([-\d.]+),([-\d.]+)\)", svg_text).group(1, 2))
    to_px = lambda x, y: (tx + sx * x, ty + sy * y)
    subpaths = []
    for d in re.findall(r' d="([^"]+)"', svg_text):
        toks = TOKEN.findall(d)
        i, cmd, cx, cy, cur, start = 0, None, 0.0, 0.0, None, (0.0, 0.0)
        while i < len(toks):
            t = toks[i]
            if t.isalpha():
                cmd = t
                i += 1
                if cmd in "Zz":
                    if cur:
                        cur.append(["Z"])
                    cx, cy = start
                continue
            n = 2 if cmd in "MmLl" else 6
            vals = list(map(float, toks[i:i + n]))
            i += n
            rel = cmd.islower()
            if cmd in "Mm":
                cx, cy = (cx + vals[0], cy + vals[1]) if rel else vals
                start = (cx, cy)
                cur = [["M", *to_px(cx, cy)]]
                subpaths.append(cur)
                cmd = "l" if rel else "L"  # implicit lineto after moveto
            elif cmd in "Ll":
                cx, cy = (cx + vals[0], cy + vals[1]) if rel else vals
                cur.append(["L", *to_px(cx, cy)])
            else:
                pts = [(cx + vals[k], cy + vals[k + 1]) if rel else (vals[k], vals[k + 1]) for k in (0, 2, 4)]
                cur.append(["C", *[c for p in pts for c in to_px(*p)]])
                cx, cy = pts[2]
    return subpaths, height


def trace(ink, threshold=INK_THRESHOLD):
    big = Image.fromarray((ink * 255).astype(np.uint8)).resize(
        (ink.shape[1] * UPSCALE, ink.shape[0] * UPSCALE), Image.LANCZOS)
    mask = np.array(big) >= threshold * 255
    with tempfile.TemporaryDirectory() as tmp:
        pbm, svg = os.path.join(tmp, "in.pbm"), os.path.join(tmp, "out.svg")
        Image.fromarray(~mask).convert("1").save(pbm)  # potrace traces black pixels
        subprocess.run(["potrace", "-s", "--turdsize", "4", "--alphamax", "1.0",
                        "--opttolerance", "0.2", "-o", svg, pbm], check=True)
        return parse_potrace_svg(open(svg).read())[0]


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def path_d(subpaths):
    return " ".join(seg[0] + " ".join(fmt(v) for v in seg[1:]) for sp in subpaths for seg in sp)


def component(name, rgb, x0, y0, threshold=INK_THRESHOLD):
    bg = background(rgb)
    ink = inkness(rgb, bg)
    tb = tight_box(ink)
    if tb is None:
        return None
    bx0, by0, bx1, by1 = tb
    rgb, ink = rgb[by0:by1, bx0:bx1], ink[by0:by1, bx0:bx1]
    # colour of the solid core of the strokes: the most-inked 20% of ink pixels
    # (averaging all ink pixels lets anti-aliased edges pull the colour toward the background)
    inked = ink > 0.2
    strong = ink >= np.percentile(ink[inked], 80) if inked.any() else ink > 0.6
    colour = rgb[strong].mean(axis=0) if strong.any() else rgb.reshape(-1, 3).mean(axis=0)
    hexcol = "#%02X%02X%02X" % tuple(int(round(c)) for c in colour)
    w, h = bx1 - bx0, by1 - by0
    ox, oy = x0 + bx0, y0 + by0

    # transparent PNG: ink colour, alpha = inkness
    rgba = np.dstack([np.broadcast_to(colour, rgb.shape).astype(np.uint8), (ink * 255).astype(np.uint8)])
    Image.fromarray(rgba).save(os.path.join(OUT, f"{name}.png"))

    # vector: local coords in 1x pixels (for the website), absolute coords (for the editors)
    local = [[[seg[0], *[v / UPSCALE for v in seg[1:]]] for seg in sp] for sp in trace(ink, threshold)]
    absolute = [[[seg[0], *[v + (ox if k % 2 == 0 else oy) for k, v in enumerate(seg[1:])]] for seg in sp] for sp in local]
    with open(os.path.join(OUT, f"{name}.svg"), "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
                f'<path fill="{hexcol}" d="{path_d(local)}"/></svg>\n')
    return {"name": name, "box": [int(ox), int(oy), int(w), int(h)], "colour": hexcol,
            "png": f"{name}.png", "svg": f"{name}.svg", "viewBox": [0, 0, int(w), int(h)],
            "d": path_d(local), "paths": [[[seg[0], *[round(v, 2) for v in seg[1:]]] for seg in sp] for sp in absolute]}


if __name__ == "__main__":
    src, spec_path, OUT = sys.argv[1:4]
    os.makedirs(OUT, exist_ok=True)
    image = np.asarray(Image.open(src).convert("RGB")).astype(float)
    manifest = []
    for item in json.load(open(spec_path)):
        x, y, w, h = item["box"]
        region = image[y:y + h, x:x + w]
        if item.get("split"):
            ink = inkness(region, background(region))
            for i, (c0, c1) in enumerate(split_columns(ink, item.get("min_gap", 30))):
                names = item.get("names") or []
                name = names[i] if i < len(names) else f'{item["name"]}_{i + 1}'
                comp = component(name, region[:, c0:c1], x + c0, y, item.get("threshold", INK_THRESHOLD))
                if comp:
                    manifest.append(comp)
        else:
            comp = component(item["name"], region, x, y, item.get("threshold", INK_THRESHOLD))
            if comp:
                manifest.append(comp)
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"))
    for c in manifest:
        print(f'{c["name"]:16} box={c["box"]} colour={c["colour"]} subpaths={len(c["paths"])}')
