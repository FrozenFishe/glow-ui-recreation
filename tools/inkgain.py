"""Pick a per-element "ink gain" (a same-colour hairline stroke) for a renderer from a stroke-width sweep.

Every renderer anti-aliases filled paths a little differently. Measured against the original, the traced
vectors come out slightly too light in all four tools (thinner anti-aliased edges), and by different amounts:
Affinity and PhotoCraft more than Photoshop. Stroking each traced path in its own fill colour with a hairline
(0.05-0.2 px) adds back the missing edge coverage without moving the shape.

Render the design in the tool once per stroke width (every traced vector stroked with that width; make_kit.py
--ink-all W, GLOW_INK_ALL=W node build.mjs, or the Affinity script's INK map), then run:

usage: inkgain.py <original> <out.json> --render 0=r0.png --render 0.1=r1.png [...] [--manifest m.json ...]
Output: {"element_name": stroke_width, ...}: the width whose render best matches the original (mean abs error
over the element's box), per element. Elements drawn as original-pixel cutouts (mode "raster") are skipped.
"""
import argparse
import json

import numpy as np
from PIL import Image

MANIFESTS = ["variants/shared/components_tuned/manifest.json", "variants/shared/text_all_tuned/manifest.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("out")
    ap.add_argument("--render", action="append", required=True, help="W=path: a render with every vector stroked at W px")
    ap.add_argument("--manifest", action="append")
    a = ap.parse_args()
    O = np.asarray(Image.open(a.original).convert("RGB"), dtype=np.float64)
    R = {}
    for r in a.render:
        w, p = r.split("=", 1)
        R[float(w)] = np.asarray(Image.open(p).convert("RGB").resize((O.shape[1], O.shape[0])), dtype=np.float64)
    elems = [c for m in (a.manifest or MANIFESTS) for c in json.load(open(m)) if c.get("mode") != "raster"]
    best, tot, totb = {}, {w: 0.0 for w in R}, 0.0
    for c in elems:
        x, y, w, h = c["box"]
        e = {k: np.abs(v[y:y + h, x:x + w] - O[y:y + h, x:x + w]).mean() for k, v in R.items()}
        b = min(e, key=e.get)
        best[c["name"]] = b
        for k in R:
            tot[k] += e[k] * w * h
        totb += e[b] * w * h
    json.dump(best, open(a.out, "w"), indent=1)
    print("total abs error by uniform width:", {k: round(v / 1e3) for k, v in sorted(tot.items())}, "| per-element best:", round(totb / 1e3))


if __name__ == "__main__":
    main()
