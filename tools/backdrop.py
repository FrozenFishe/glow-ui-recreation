"""Extract the design's empty background ("backdrop") as a small image.

Masks everything that isn't background (traced components, text blocks, known
shapes, photos), averages the remaining pixels in cells of CELL x CELL px, and
fills the masked cells by diffusion from their neighbours. The result is a
tiny image (1536x1024 / CELL) that, stretched back to full size, reproduces
the background's real 2D shading instead of a hand-fitted gradient.

usage: backdrop.py <design> <out.png> --manifest m1.json [--manifest m2.json] --mask x,y,w,h [...] [--cell 8]
"""
import argparse
import json

import numpy as np
from PIL import Image, ImageFilter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("out")
    ap.add_argument("--manifest", action="append", default=[])
    ap.add_argument("--mask", action="append", default=[], help="x,y,w,h of a non-background area (photo, shape)")
    ap.add_argument("--cell", type=int, default=8)
    ap.add_argument("--pad", type=int, default=4, help="grow masks by this many px (anti-aliased edges, shadows)")
    ap.add_argument("--plate", help="also write a full-resolution background plate: the original's own background pixels\n"
                    "wherever nothing is drawn on top, and the smooth backdrop under the masked foreground")
    ap.add_argument("--plate-pad", type=int, default=3, help="extra px around the foreground left to the smooth backdrop in the plate")
    a = ap.parse_args()

    im = np.asarray(Image.open(a.design).convert("RGB"), dtype=np.float64)
    H, W = im.shape[:2]
    mask = np.zeros((H, W), bool)
    for m in a.manifest:
        for c in json.load(open(m)):
            x, y, w, h = c["box"]
            mask[max(y - a.pad, 0):y + h + a.pad, max(x - a.pad, 0):x + w + a.pad] = True
    for s in a.mask:
        x, y, w, h = map(int, s.split(","))
        mask[max(y - a.pad, 0):y + h + a.pad, max(x - a.pad, 0):x + w + a.pad] = True
    # anything that still stands out from its neighbourhood (hairlines, borders) is not background
    grey = np.asarray(Image.fromarray(im.astype(np.uint8)).convert("L"), dtype=np.float64)
    local = np.asarray(Image.fromarray(grey.astype(np.uint8)).filter(ImageFilter.MedianFilter(15)), dtype=np.float64)
    boxes = mask.copy()  # traced elements + given shapes/photos
    edges = np.abs(grey - local) > 12  # real edges and hairlines (JPEG grain stays below this)
    mask |= np.abs(grey - local) > 4
    mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0

    C = a.cell
    h, w = H // C, W // C
    field = np.zeros((h, w, 3))
    known = np.zeros((h, w), bool)
    for j in range(h):
        for i in range(w):
            m = ~mask[j * C:(j + 1) * C, i * C:(i + 1) * C]
            if m.mean() > 0.5:
                field[j, i] = im[j * C:(j + 1) * C, i * C:(i + 1) * C][m].mean(axis=0)
                known[j, i] = True
    # fill unknown cells by diffusion (repeated neighbour averaging), known cells fixed
    filled = field.copy()
    filled[~known] = field[known].mean(axis=0)
    for _ in range(400):
        p = np.pad(filled, ((1, 1), (1, 1), (0, 0)), mode="edge")
        avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
        filled[~known] = avg[~known]
    small = Image.fromarray(np.clip(np.round(filled), 0, 255).astype(np.uint8))
    small.save(a.out)
    if a.plate:
        smooth = np.asarray(small.resize((W, H), Image.BILINEAR), dtype=np.float64)
        fgm = boxes | edges
        fg = np.asarray(Image.fromarray(fgm.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * a.plate_pad + 1))) > 0
        plate = np.where(fg[..., None], smooth, im)
        Image.fromarray(np.clip(np.round(plate), 0, 255).astype(np.uint8)).save(a.plate, lossless=True) if a.plate.endswith(".webp") \
            else Image.fromarray(np.clip(np.round(plate), 0, 255).astype(np.uint8)).save(a.plate)
        print(f"plate {W}x{H}: {100 - fg.mean() * 100:.0f}% original background pixels, rest from the smooth backdrop")
    print(f"backdrop {w}x{h} (cell {C}px), {known.mean() * 100:.0f}% of cells measured, rest filled")


if __name__ == "__main__":
    main()
