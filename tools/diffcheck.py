"""Measure how closely a recreation matches the original, region by region.

Aligns nothing and forgives nothing: both images are compared at the original's
size. For each region it reports a similarity score (1 - mean absolute colour
difference after a 1px blur, so anti-aliasing noise doesn't count) and the
share of pixels that differ by more than 12%. It also finds, per region, the
sub-pixel shift that would best line the recreation up with the original: if a
shift removes most of the difference, the content is right but misplaced, and
the shift is the exact correction. Writes a heatmap and a worst-first list.

usage: diffcheck.py <original> <recreation> [--regions regions.json] [--out diff.png] [--json report.json]

regions.json: {"nav": [x, y, w, h], ...}  (defaults to a 6x4 grid)
"""
import argparse
import json

import numpy as np
from PIL import Image, ImageFilter


def load(path, size=None):
    im = Image.open(path).convert("RGB")
    if size and im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 255.0


def best_shift(o, r, x, y, w, h, reach=8, step=0.5):
    """Sub-pixel (dx, dy) that best lines the recreation up with the original in this region.
    If it removes most of the difference, the content is right but misplaced: move it by (dx, dy)."""
    H, W = o.shape[:2]
    pad = reach + 2
    x0, y0, x1, y1 = max(x - pad, 0), max(y - pad, 0), min(x + w + pad, W), min(y + h + pad, H)
    rim = Image.fromarray((r[y0:y1, x0:x1] * 255).astype(np.uint8))
    ox, oy = x - x0, y - y0
    target = o[y:y + h, x:x + w]
    best = (0.0, 0.0, 1.0)
    def changed(dx, dy):
        # content moved by (dx, dy): sample the recreation at (u - dx, v - dy)
        m = rim.transform(rim.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR)
        c = np.asarray(m, dtype=np.float32)[oy:oy + h, ox:ox + w] / 255.0
        return float((np.abs(target - c).mean(axis=2) > 0.12).mean())
    for dy in np.arange(-reach, reach + 1, 1.0):
        for dx in np.arange(-reach, reach + 1, 1.0):
            v = changed(dx, dy)
            if v < best[2]:
                best = (dx, dy, v)
    bx, by = best[0], best[1]
    for dy in np.arange(by - 1, by + 1.01, step):
        for dx in np.arange(bx - 1, bx + 1.01, step):
            v = changed(dx, dy)
            if v < best[2]:
                best = (float(dx), float(dy), v)
    return round(float(best[0]), 1), round(float(best[1]), 1), best[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("recreation")
    ap.add_argument("--regions")
    ap.add_argument("--out", default="diff.png")
    ap.add_argument("--json")
    a = ap.parse_args()

    size = Image.open(a.original).size
    o, r = load(a.original), load(a.recreation, size)
    d = np.abs(o - r).mean(axis=2)  # 0..1 per pixel

    if a.regions:
        regions = json.load(open(a.regions))
    else:
        W, H = size
        regions = {f"r{j}c{i}": [i * W // 6, j * H // 4, W // 6, H // 4] for j in range(4) for i in range(6)}

    rows = []
    for name, (x, y, w, h) in regions.items():
        cell = d[y:y + h, x:x + w]
        dx, dy, best = best_shift(o, r, x, y, w, h)
        rows.append({"region": name, "box": [x, y, w, h], "similarity": round(1 - float(cell.mean()), 4),
                     "changed_pct": round(float((cell > 0.12).mean() * 100), 2),
                     "shift": [dx, dy], "changed_pct_if_shifted": round(best * 100, 2)})
    rows.sort(key=lambda r: r["changed_pct"], reverse=True)
    overall = {"similarity": round(1 - float(d.mean()), 4), "changed_pct": round(float((d > 0.12).mean() * 100), 2)}

    # heatmap: original in grey, differences in red
    grey = (o.mean(axis=2) * 0.55 + 0.45)[..., None].repeat(3, axis=2)
    heat = np.clip(d / 0.25, 0, 1)[..., None]
    img = grey * (1 - heat) + np.array([0.9, 0.1, 0.1]) * heat
    Image.fromarray((img * 255).astype(np.uint8)).save(a.out)

    print(f"overall similarity {overall['similarity']:.4f}  changed {overall['changed_pct']:.2f}%")
    for r in rows[:12]:
        hint = f"  -> move by {r['shift']} to reach {r['changed_pct_if_shifted']:.2f}%" if r["changed_pct"] - r["changed_pct_if_shifted"] > 1 else ""
        print(f"  {r['region']:18} changed {r['changed_pct']:6.2f}%  similarity {r['similarity']:.4f}{hint}")
    if a.json:
        json.dump({"overall": overall, "regions": rows}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
