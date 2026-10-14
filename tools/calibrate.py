"""Calibrate drawn shapes against a tool's actual render (renderer in the loop).

Shapes are tuned against a simulated renderer, but every tool (browser, Affinity,
PhotoCraft, Photoshop) anti-aliases and positions a little differently, and some
layouts nest shapes so a correction can land twice. This measures, in the tool's
real export, where each edge of each shape landed compared with the original:
for each of the four edges it takes a band across the edge (avoiding corners and
masking text, icons and photos) and finds the 1D shift, in 1/8 px steps, that
best matches the original. Left/right shifts become dx and dw, top/bottom
become dy and dh. Run it, apply the corrections, re-render, and repeat.

usage: calibrate.py <original> <render.png> <shapes.json> <out.json>
                    [--exclude manifest.json ...] [--exclude-box x,y,w,h ...] [--prev calib.json]
Output: {"shape_name": {"dx":..,"dy":..,"dw":..,"dh":..}, ...}, accumulated onto --prev if given.
"""
import argparse
import json

import numpy as np
from PIL import Image

STEPS = np.arange(-2.0, 2.001, 0.125)
BAND = 4  # px either side of the edge


def shift1d(arr, s, axis):
    """Shift an array along an axis by s px (linear interpolation, edge-clamped)."""
    n = arr.shape[axis]
    idx = np.arange(n) - s
    i0 = np.clip(np.floor(idx).astype(int), 0, n - 1)
    i1 = np.clip(i0 + 1, 0, n - 1)
    f = (idx - np.floor(idx)).reshape([-1 if k == axis else 1 for k in range(arr.ndim)])
    return np.take(arr, i0, axis=axis) * (1 - f) + np.take(arr, i1, axis=axis) * f


def best_edge_shift(orig, rend, valid, axis):
    if valid.sum() < 6:
        return 0.0, 0.0
    errs = []
    for s in STEPS:
        r = shift1d(rend, s, axis)
        errs.append(np.abs(r - orig).mean(axis=2)[valid].mean())
    k = int(np.argmin(errs))
    return float(STEPS[k]), float(errs[len(STEPS) // 2] - errs[k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("render")
    ap.add_argument("shapes")
    ap.add_argument("out")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--exclude-box", action="append", default=[])
    ap.add_argument("--prev", help="previous calibration to accumulate onto")
    ap.add_argument("--min-gain", type=float, default=0.15, help="ignore shifts that improve the band by less than this")
    ap.add_argument("--damping", type=float, default=0.6, help="apply this fraction of each measured shift per round")
    a = ap.parse_args()
    O = np.asarray(Image.open(a.original).convert("RGB"), dtype=np.float64)
    R = np.asarray(Image.open(a.render).convert("RGB").resize((O.shape[1], O.shape[0])), dtype=np.float64)
    H, W = O.shape[:2]
    covered = np.zeros((H, W), bool)
    for m in a.exclude:
        for c in json.load(open(m)):
            x, y, w, h = c.get("raster_box") or c["box"]
            covered[y:y + h, x:x + w] = True
    for b in a.exclude_box:
        x, y, w, h = map(int, b.split(","))
        covered[y:y + h, x:x + w] = True
    prev = json.load(open(a.prev)) if a.prev else {}
    out = {}
    for s in json.load(open(a.shapes)):
        x, y, w, h = s["box"]
        r = s.get("r", 0) if s["kind"] == "rect" else min(w, h) / 2
        res = {}
        # vertical edges (left/right): rows away from the corners
        y0, y1 = int(round(y + max(r, 2))), int(round(y + h - max(r, 2)))
        for side, ex in (("L", x), ("R", x + w)):
            cx0, cx1 = int(np.floor(ex)) - BAND, int(np.ceil(ex)) + BAND
            if y1 - y0 < 2 or cx0 < 0 or cx1 > W:
                res[side] = (0.0, 0.0); continue
            res[side] = best_edge_shift(O[y0:y1, cx0:cx1], R[y0:y1, cx0:cx1], ~covered[y0:y1, cx0:cx1], axis=1)
        xa, xb = int(round(x + max(r, 2))), int(round(x + w - max(r, 2)))
        for side, ey in (("T", y), ("B", y + h)):
            cy0, cy1 = int(np.floor(ey)) - BAND, int(np.ceil(ey)) + BAND
            if xb - xa < 2 or cy0 < 0 or cy1 > H:
                res[side] = (0.0, 0.0); continue
            res[side] = best_edge_shift(O[cy0:cy1, xa:xb], R[cy0:cy1, xa:xb], ~covered[cy0:cy1, xa:xb], axis=0)
        # a positive shift s means the render's content should move by +s
        g = lambda k: res[k][0] * a.damping if res[k][1] >= a.min_gain else 0.0
        sL, sR, sT, sB = g("L"), g("R"), g("T"), g("B")
        p = prev.get(s["name"], {"dx": 0, "dy": 0, "dw": 0, "dh": 0})
        out[s["name"]] = {"dx": round(p["dx"] + sL, 3), "dy": round(p["dy"] + sT, 3),
                          "dw": round(p["dw"] + sR - sL, 3), "dh": round(p["dh"] + sB - sT, 3)}
        if any([sL, sR, sT, sB]):
            print(f'{s["name"]:16} edges L{sL:+.3f} R{sR:+.3f} T{sT:+.3f} B{sB:+.3f} -> total {out[s["name"]]}')
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
