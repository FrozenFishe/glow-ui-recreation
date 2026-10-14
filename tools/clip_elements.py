"""Clip traced elements to the region they belong to.

An element's box can overlap a neighbouring edge: the "TRUSTED BY" arc sits inside the badge, but its box
reaches the badge's grey rim, so the trace picks up rim fragments and the original-pixel cutout paints the rim in
the text colour. A clip removes the subpaths whose centre falls outside the region and zeroes the cutout's
alpha outside it. Regions: {"circle": [cx, cy, r]} or {"rect": [x, y, w, h]}, in design px.

usage: clip_elements.py <tuned-manifest.json> <clips.json>      (edits the manifest, its SVGs and cutouts in place)
clips.json: [{"name": "tx_badge_arc", "circle": [1429.6, 802.9, 66.5]}, ...]
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slicer import path_d  # noqa: E402


def inside(clip, x, y):
    if "circle" in clip:
        cx, cy, r = clip["circle"]
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
    rx, ry, rw, rh = clip["rect"]
    return (rx <= x) & (x <= rx + rw) & (ry <= y) & (y <= ry + rh)


def main():
    manifest, clips_file = sys.argv[1:3]
    d = os.path.dirname(manifest)
    comps = json.load(open(manifest))
    by = {c["name"]: c for c in comps}
    for clip in json.load(open(clips_file)):
        c = by.get(clip["name"])
        if not c:
            continue
        keep = []
        for sp in c["paths"]:
            pts = np.array([v for s in sp for v in s[1:]], float).reshape(-1, 2)
            if inside(clip, *pts.mean(axis=0)):
                keep.append(sp)
        px, py = c["box"][:2]
        removed = len(c["paths"]) - len(keep)
        c["paths"] = keep
        c["d"] = path_d([[[s[0], *[v - (px if k % 2 == 0 else py) for k, v in enumerate(s[1:])]] for s in sp] for sp in keep])
        w, h = c["box"][2:]
        open(os.path.join(d, c["svg"]), "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><path fill="{c["colour"]}" d="{c["d"]}"/></svg>\n')
        zeroed = 0
        if c.get("raster"):
            rp = os.path.join(d, c["raster"])
            im = np.array(Image.open(rp).convert("RGBA"))
            X0, Y0 = c["raster_box"][:2]
            yy, xx = np.mgrid[0:im.shape[0], 0:im.shape[1]]
            out = ~inside(clip, xx + X0 + 0.5, yy + Y0 + 0.5) & (im[..., 3] > 0)
            zeroed = int(out.sum())
            im[out, 3] = 0
            Image.fromarray(im).save(rp)
        c["clip"] = {k: v for k, v in clip.items() if k != "name"}
        print(f'{c["name"]}: removed {removed} of {removed + len(keep)} subpaths, zeroed {zeroed} cutout pixels outside the clip')
    json.dump(comps, open(manifest, "w"))


if __name__ == "__main__":
    main()
