"""Exact mode for the website: the editor's exact layers (exported from PhotoCraft) as page background layers.

The site's desktop page is two boxes: the stage (design rows 0..split) and the brand strip (split..H). Each
exported layer (design-sized PNG, placed at 0,0) is cut at the split, trimmed to its opaque pixels and written
as a lossless WebP. build.mjs stacks them as multiple CSS backgrounds, so at 1x the page is the original bit for
bit while every link, field and button stays live on top (their text is transparent, as in pixel mode).

usage: web_exact.py <layers-dir> <out-dir> [--split 894]
The layers dir holds NN_<section>.png (00 = background, opaque); a higher NN paints above a lower one.
Writes <out-dir>/*.webp and <out-dir>/exact.json ({W, H, split, layers: [{name, part, file, box}] bottom to top}).
"""
import argparse
import glob
import json
import os

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("layers")
ap.add_argument("out")
ap.add_argument("--split", type=int, default=894)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)

files = sorted(glob.glob(os.path.join(a.layers, "[0-9][0-9]_*.png")))
W, H = Image.open(files[0]).size
out, comp = [], {}
for f in files:
    name = os.path.splitext(os.path.basename(f))[0]
    im = Image.open(f).convert("RGBA")
    for part, (y0, y1) in (("stage", (0, a.split)), ("brands", (a.split, H))):
        piece = im.crop((0, y0, W, y1))
        alpha = np.asarray(piece)[..., 3]
        if alpha.max() == 0:
            continue
        if alpha.min() not in (0, 255) or not set(np.unique(alpha)) <= {0, 255}:
            raise SystemExit(f"{name}: partial alpha; exact layers must be opaque or empty per pixel")
        box = Image.fromarray(alpha).getbbox()
        cut = piece.crop(box)
        if alpha[box[1]:box[3], box[0]:box[2]].min() == 255:
            cut = cut.convert("RGB")
        fn = f"{name}_{part}.webp"
        cut.save(os.path.join(a.out, fn), lossless=True, quality=100, method=6, exact=True)
        x, y = box[0], box[1]
        out.append({"name": name, "part": part, "file": fn, "box": [x, y + y0, box[2] - box[0], box[3] - box[1]]})
        # check the round trip: the WebP must decode to the same opaque pixels
        back = np.asarray(Image.open(os.path.join(a.out, fn)).convert("RGBA"))
        src = np.asarray(cut.convert("RGBA"))
        m = src[..., 3] == 255
        assert (back[m] == src[m]).all() and (back[..., 3][m] == 255).all(), fn

json.dump({"W": W, "H": H, "split": a.split, "layers": out}, open(os.path.join(a.out, "exact.json"), "w"), indent=1)
for l in out:
    print(f"{l['file']:32s} {l['box']}  {os.path.getsize(os.path.join(a.out, l['file'])) // 1024} KB")
