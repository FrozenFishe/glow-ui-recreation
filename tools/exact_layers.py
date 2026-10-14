"""Exact mode: decompose the original into named, editable layers that composite back to it bit for bit.

A redraw (vectors, shapes, text) can't reach a literal 0% difference: every renderer anti-aliases edges its
own way. Exact mode is a different deliverable. It splits the original's own pixels into a background layer
plus one layer per section of the page, so the default view is pixel-identical while each section can still be
hidden, moved or edited, and the rebuilt vector version stays underneath, one visibility toggle away.

  00_background.png   the background plate (tools/backdrop.py --plate): the original's pixels wherever the
                      background shows, a smooth fill under the foreground. Opaque, full canvas.
  NN_<section>.png    the original's pixels over that section's foreground, opaque, transparent elsewhere.
                      Sections partition the canvas, so stacking them in any order reproduces the original.

usage: exact_layers.py <original> <backdrop_plate> <out-dir>
Writes the PNGs (all 1536x1024, place at 0,0) and layers.json (bottom to top). Lossless PNG only.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

W, H = 1536, 1024


def sections():
    """Section ownership, in priority order (the first section that claims a pixel owns it)."""
    yy, xx = np.mgrid[0:H, 0:W]
    claimed = np.zeros((H, W), bool)
    out = []
    for name, region in [
        ("Badge", (xx + 0.5 - 1430) ** 2 + (yy + 0.5 - 802) ** 2 <= 74 ** 2),
        ("Phone", (xx >= 1068) & (xx < 1398) & (yy >= 174) & (yy < 877)),
        ("Brand strip", yy >= 892),
        ("Hero photo", xx >= 712),
        ("Navigation", yy < 110),
        ("Search bar", (yy >= 530) & (yy < 640)),
        ("Hero copy", yy < 530),
        ("Features", np.ones((H, W), bool)),
    ]:
        own = region & ~claimed
        claimed |= own
        out.append((name, own))
    return out


def main():
    orig_p, plate_p, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    O = np.asarray(Image.open(orig_p).convert("RGB"))
    P = np.asarray(Image.open(plate_p).convert("RGB"))
    assert O.shape == P.shape == (H, W, 3)
    fg = (O != P).any(axis=2)  # where the plate isn't already the original
    Image.fromarray(P).save(os.path.join(out, "00_background.png"))
    layers = [{"name": "Background (original pixels + smooth fill)", "file": "00_background.png"}]
    comp = P.copy()
    for i, (name, own) in enumerate(sections(), 1):
        m = own & fg
        rgba = np.zeros((H, W, 4), np.uint8)
        rgba[..., :3] = np.where(m[..., None], O, 0)
        rgba[..., 3] = m * 255
        f = f"{i:02d}_{name.lower().replace(' ', '_')}.png"
        Image.fromarray(rgba).save(os.path.join(out, f))
        layers.append({"name": f"{name} (original pixels)", "file": f, "pixels": int(m.sum())})
        comp[m] = O[m]
    json.dump(layers, open(os.path.join(out, "layers.json"), "w"), indent=1)
    diff = int((comp != O).any(axis=2).sum())
    print(f"{len(layers)} layers in {out}; foreground {fg.mean() * 100:.1f}% of canvas; recomposited vs original: {diff} pixels differ")
    for l in layers[1:]:
        print(f'  {l["name"]:40} {l["pixels"]:7d} px')


if __name__ == "__main__":
    main()
