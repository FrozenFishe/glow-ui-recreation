"""Auto-tune traced components so they render as close to the original as possible.

For every component in a slicer manifest it searches:
  - the trace threshold (how far into the anti-aliased edge the outline sits),
  - a sub-pixel offset (1/8 px steps),
  - the fill colour: solved in closed form (least squares) for the coverage of
    each candidate, composited over the local background,
scoring each candidate by simulating the render (8x supersampled rasterisation
with even-odd fill) against the original pixels. Tiny components can instead
use an original-pixel cutout ("raster" mode) when that is clearly closer; their
vector is kept for high-DPI screens and editors.

usage: tune.py <design> <manifest.json> <out-dir> [--raster-max 18]
Writes <out-dir>/manifest.json (same format as slicer.py, plus a "tune" record)
and the tuned SVG/PNG files.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from slicer import UPSCALE, background, inkness, path_d, trace  # noqa: E402

SS = 8          # supersampling for the simulated render
PAD = 3         # px around each component
THRESHOLDS = (0.3, 0.38, 0.45, 0.5, 0.55, 0.62, 0.7)
OFFSETS = [i / SS for i in (-2, -1, 0, 1, 2)]


def flatten(sp, scale, dx, dy):
    pts, cur = [], None
    for seg in sp:
        if seg[0] == "M":
            cur = (seg[1], seg[2]); pts.append(cur)
        elif seg[0] == "L":
            cur = (seg[1], seg[2]); pts.append(cur)
        elif seg[0] == "C":
            p0, p1, p2, p3 = cur, (seg[1], seg[2]), (seg[3], seg[4]), (seg[5], seg[6])
            for t in np.linspace(0, 1, 9)[1:]:
                u = 1 - t
                pts.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                            u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
            cur = p3
    return [((x + dx) * scale, (y + dy) * scale) for x, y in pts]


def coverage(subpaths, w, h, dx=0.0, dy=0.0):
    """Even-odd coverage (0..1) of local-coordinate subpaths, at 1x, via 8x supersampling."""
    acc = np.zeros((h * SS, w * SS), bool)
    for sp in subpaths:
        poly = flatten(sp, SS, dx, dy)
        if len(poly) < 3:
            continue
        m = Image.new("1", (w * SS, h * SS), 0)
        ImageDraw.Draw(m).polygon(poly, fill=1)
        acc ^= np.asarray(m, bool)
    return acc.reshape(h, SS, w, SS).mean(axis=(1, 3))


def best_colour(alpha, orig, bg):
    a = alpha[..., None]
    num = (a * (orig - bg * (1 - a))).sum(axis=(0, 1))
    den = (a * a).sum(axis=(0, 1)) + 1e-9
    return np.clip(num / den, 0, 255)


def err(alpha, colour, orig, bg):
    comp = bg * (1 - alpha[..., None]) + colour * alpha[..., None]
    return float(np.abs(comp - orig).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("manifest")
    ap.add_argument("out")
    ap.add_argument("--raster-max", type=int, default=18, help="components whose shorter side is at most this many px may use original-pixel cutouts")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    img = np.asarray(Image.open(a.design).convert("RGB"), dtype=np.float64)
    H, W = img.shape[:2]
    src_dir = os.path.dirname(a.manifest)
    out = []
    totals = {"before": 0.0, "after": 0.0}

    for c in json.load(open(a.manifest)):
        x, y, w, h = c["box"]
        X0, Y0 = max(x - PAD, 0), max(y - PAD, 0)
        X1, Y1 = min(x + w + PAD, W), min(y + h + PAD, H)
        rw, rh = X1 - X0, Y1 - Y0
        orig = img[Y0:Y1, X0:X1]
        bg = background(orig)
        ink = inkness(orig, bg)

        # current state: manifest paths in region-local coords, manifest colour
        cur = [[[s[0], *[v - (X0 if k % 2 == 0 else Y0) for k, v in enumerate(s[1:])]] for s in sp] for sp in c["paths"]]
        hexc = c["colour"].lstrip("#")
        cur_col = np.array([int(hexc[i:i + 2], 16) for i in (0, 2, 4)], float)
        e_before = err(coverage(cur, rw, rh), cur_col, orig, bg)

        best = (e_before, None)
        for t in THRESHOLDS:
            local = [[[s[0], *[v / UPSCALE for v in s[1:]]] for s in sp] for sp in trace(ink, t)]
            if not local:
                continue
            for dy in OFFSETS:
                for dx in OFFSETS:
                    al = coverage(local, rw, rh, dx, dy)
                    if al.sum() < 1:
                        continue
                    col = best_colour(al, orig, bg)
                    e = err(al, col, orig, bg)
                    if e < best[0]:
                        best = (e, (t, dx, dy, local, col))

        rec = dict(c)
        if best[1]:
            t, dx, dy, local, col = best[1]
            local = [[[s[0], *[v + (dx if k % 2 == 0 else dy) for k, v in enumerate(s[1:])]] for s in sp] for sp in local]
            hexcol = "#%02X%02X%02X" % tuple(int(round(v)) for v in col)
            rec.update(box=[X0, Y0, rw, rh], viewBox=[0, 0, rw, rh], colour=hexcol, d=path_d(local),
                       paths=[[[s[0], *[round(v + (X0 if k % 2 == 0 else Y0), 3) for k, v in enumerate(s[1:])]] for s in sp] for sp in local])
            with open(os.path.join(a.out, c["svg"]), "w") as f:
                f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {rw} {rh}" width="{rw}" height="{rh}"><path fill="{hexcol}" d="{rec["d"]}"/></svg>\n')
        else:  # nothing beat the current trace: keep it, but still write its SVG next to the tuned manifest
            import shutil
            shutil.copyfile(os.path.join(src_dir, c["svg"]), os.path.join(a.out, c["svg"]))
        e_after = best[0]

        # raster candidate for tiny components: original pixels with alpha = ink, colour solved the same way
        # every element also gets an original-pixel cutout (used for tiny elements by default,
        # and for everything in max-fidelity mode); tiny ones use it when it's clearly closer
        mode = "vector"
        col_r = best_colour(ink, orig, bg)
        e_r = err(ink, col_r, orig, bg)
        rgba = np.dstack([np.broadcast_to(col_r, orig.shape).astype(np.uint8), (ink * 255).astype(np.uint8)])
        Image.fromarray(rgba).save(os.path.join(a.out, c["name"] + "-raster.png"))
        rec["raster"] = c["name"] + "-raster.png"
        rec["raster_box"] = [X0, Y0, rw, rh]
        rec["raster_err"] = round(e_r, 3)
        if min(w, h) <= a.raster_max and e_r < e_after * 0.7:
            mode = "raster"
            e_after = min(e_after, e_r)
        rec["mode"] = mode
        rec["tune"] = {"err_before": round(e_before, 3), "err_after": round(e_after, 3),
                       **({"threshold": best[1][0], "dx": best[1][1], "dy": best[1][2]} if best[1] else {})}
        totals["before"] += e_before * rw * rh
        totals["after"] += e_after * rw * rh
        out.append(rec)
        print(f'{c["name"]:24} err {e_before:6.2f} -> {e_after:6.2f}  {mode}'
              + (f'  t={best[1][0]} dx={best[1][1]:+.3f} dy={best[1][2]:+.3f}' if best[1] else "  (kept)"))

    json.dump(out, open(os.path.join(a.out, "manifest.json"), "w"))
    print(f'area-weighted error {totals["before"]:.0f} -> {totals["after"]:.0f} '
          f'({(1 - totals["after"] / max(totals["before"], 1e-9)) * 100:.0f}% lower)')


if __name__ == "__main__":
    main()
