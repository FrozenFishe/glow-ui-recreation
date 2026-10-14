"""Split parts that don't trace well out of a traced element into their own tiny original-pixel elements.

Some logo parts can't be drawn as a single-colour vector at 1x: the 4px "SAN FRANCISCO" tagline under the
benefit wordmark drops out of the trace entirely, and the elleebana tree mark is multi-tone (a shaded canopy),
so its flat trace is one grey blob. Each part listed in the parts file becomes its own element: a traced
vector (kept for 2x / editing) plus an original-pixel cutout, in "raster" mode like every other tiny element.
With "cut_parent", the parent's subpaths inside the part's box are removed so the two don't double up.
Parts carry "part_of": max-fidelity mode skips them, since the parent's full cutout already contains them.

usage: split_parts.py <design> <tuned-manifest.json> <parts.json>      (edits the manifest and its SVGs in place)
parts.json: [{"parent": "logo_benefit", "name": "logo_benefit_tagline", "box": [x, y, w, h], "cut_parent": false}, ...]
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slicer import UPSCALE, background, inkness, path_d, trace  # noqa: E402

PAD = 2


def svg(rec):
    w, h = rec["box"][2:]
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><path fill="{rec["colour"]}" d="{rec["d"]}"/></svg>\n'


def main():
    design, manifest, parts_file = sys.argv[1:4]
    out_dir = os.path.dirname(manifest)
    img = np.asarray(Image.open(design).convert("RGB"), dtype=np.float64)
    H, W = img.shape[:2]
    comps = json.load(open(manifest))
    by = {c["name"]: c for c in comps}
    for p in json.load(open(parts_file)):
        parent = by[p["parent"]]
        x, y, w, h = p["box"]
        X0, Y0, X1, Y1 = max(x - PAD, 0), max(y - PAD, 0), min(x + w + PAD, W), min(y + h + PAD, H)
        orig = img[Y0:Y1, X0:X1]
        bg = background(orig)
        ink = inkness(orig, bg)
        # pixels outside the part's own box belong to the parent (or to nothing): no ink there
        mask = np.zeros(ink.shape, bool)
        mask[y - Y0:y - Y0 + h, x - X0:x - X0 + w] = True
        ink = np.where(mask, ink, 0)
        a = ink[..., None]
        col = np.clip((a * (orig - bg * (1 - a))).sum(axis=(0, 1)) / ((a * a).sum(axis=(0, 1)) + 1e-9), 0, 255)
        hexcol = "#%02X%02X%02X" % tuple(int(round(v)) for v in col)
        rgba = np.dstack([np.broadcast_to(col, orig.shape).astype(np.uint8), (ink * 255).astype(np.uint8)])
        Image.fromarray(rgba).save(os.path.join(out_dir, p["name"] + "-raster.png"))
        local = [[[s[0], *[v / UPSCALE for v in s[1:]]] for s in sp] for sp in trace(ink, 0.5)]
        rec = {"name": p["name"], "part_of": p["parent"], "box": [X0, Y0, X1 - X0, Y1 - Y0], "viewBox": [0, 0, X1 - X0, Y1 - Y0],
               "colour": hexcol, "d": path_d(local), "svg": p["name"] + ".svg", "mode": "raster",
               "paths": [[[s[0], *[round(v + (X0 if k % 2 == 0 else Y0), 3) for k, v in enumerate(s[1:])]] for s in sp] for sp in local],
               "raster": p["name"] + "-raster.png", "raster_box": [X0, Y0, X1 - X0, Y1 - Y0]}
        open(os.path.join(out_dir, rec["svg"]), "w").write(svg(rec))
        if p.get("cut_parent"):
            def inside(sp):
                pts = np.array([v for s in sp for v in s[1:]], float).reshape(-1, 2)
                cx, cy = pts.mean(axis=0)
                return x <= cx <= x + w and y <= cy <= y + h
            keep = [sp for sp in parent["paths"] if not inside(sp)]
            print(f'{p["parent"]}: removed {len(parent["paths"]) - len(keep)} of {len(parent["paths"])} subpaths inside {p["name"]}')
            px, py = parent["box"][:2]
            parent["paths"] = keep
            parent["d"] = path_d([[[s[0], *[v - (px if k % 2 == 0 else py) for k, v in enumerate(s[1:])]] for s in sp] for sp in keep])
            open(os.path.join(out_dir, parent["svg"]), "w").write(svg(parent))
        by[p["name"]] = rec
        comps = [c for c in comps if c["name"] != p["name"]]
        comps.insert(comps.index(parent) + 1, rec)
        print(f'{p["name"]}: box {rec["box"]}, colour {hexcol}, {len(local)} traced subpaths')
    json.dump(comps, open(manifest, "w"))


if __name__ == "__main__":
    main()
