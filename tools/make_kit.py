"""Build the editor import kit: everything an editor needs to rebuild the design, as files that
any of them can place (Photoshop, PhotoCraft, Affinity, Illustrator...).

  backdrop.png                      the original's background shading (from framework/backdrop.png)
  backdrop_plate.png                full-resolution background plate: original background pixels where visible,
                                    the smooth backdrop under foreground elements (use instead of backdrop.png)
  strip_edge.png                    rows 892-895 of the original, full width: the photo's bottom edge and the
                                    brand strip's hairline, which blend there (place at 0,892 above the hero)
  hero_exact.png, thumb_*_exact.png lossless photo slices
  shapes_tuned.svg                  every drawn shape, geometry/colours from tools/glow_shapes_tuned.json
  shapes_tuned.json                 the same shapes as data (with --calibration applied)
  vectors_tuned.svg                 tuned vectors for elements drawn as vectors
  vectors_tiny_hidden.svg           tuned vectors for tiny elements (hide; for 2x / editing)
  vectors_all.svg                   both of the above
  cutouts_tiny.png                  original-pixel cutouts of the tiny elements (standard mode)
  cutouts_all_max_fidelity.png      original-pixel cutouts of every traced element (max-fidelity mode)

All files are 1536x1024 design coordinates. Layer order, bottom to top: backdrop, hero, strip edge, shapes,
card photos, vectors, tiny cutouts (+ hidden max-fidelity cutouts).

usage: make_kit.py <out-dir> [--calibration calib.json] [--ink ink.json | --ink-all W]
  --calibration applies a per-renderer correction from tools/calibrate.py to the shapes (shapes_tuned.svg)
  --ink         strokes each traced vector in its own colour with the per-element width from tools/inkgain.py
  --ink-all W   strokes every traced vector with width W (for the sweep that tools/inkgain.py reads)
  --no-clean-rims  keep the hero slice's own edges under the drawn shapes (tools/clean_rims.py)
  --photo-edges N  inset the shapes drawn over the hero photo by N px so their outline is the photo's own (implies --no-clean-rims)
"""
import copy
import json
import os
import sys

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def densify(pts, step=0.5):
    """Closed polyline with a point at least every `step` px."""
    import numpy as np
    out = []
    for a, b in zip(pts, np.roll(pts, -1, axis=0)):
        n = max(int(np.ceil(np.hypot(*(b - a)) / step)), 1)
        out.extend(a + (b - a) * t for t in np.arange(n) / n)
    return np.array(out)


def minus_disc(pts, cx, cy, r):
    """Outline of (convex polygon) minus (disc), as a polygon: the run of outline points inside the disc is
    replaced by the disc's arc between where the outline enters and leaves it. Plain path geometry, so it works
    in every SVG importer (Photoshop's ignores masks and clip paths)."""
    import numpy as np
    pts = densify(pts)
    ins = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) < r
    if not ins.any() or ins.all():
        return pts
    i0 = int(np.argmax(~ins))  # rotate so the list starts outside the disc
    pts, ins = np.roll(pts, -i0, axis=0), np.roll(ins, -i0)
    a, b = int(np.argmax(ins)), len(ins) - int(np.argmax(ins[::-1]))  # the inside run is [a, b)
    ang = lambda q: np.arctan2(q[1] - cy, q[0] - cx)
    t0, t1 = ang(pts[a - 1]), ang(pts[b % len(pts)])
    mid = pts[(a + b) // 2]  # the arc goes the way that passes the dropped run (inside the polygon)
    d = (t1 - t0) % (2 * np.pi)
    if np.hypot(*(np.array([cx + r * np.cos(t0 + d / 2), cy + r * np.sin(t0 + d / 2)]) - mid)) > \
       np.hypot(*(np.array([cx + r * np.cos(t0 + d / 2 - np.pi), cy + r * np.sin(t0 + d / 2 - np.pi)]) - mid)):
        d -= 2 * np.pi
    n = max(int(abs(d) * r / 0.5), 2)
    arc = np.array([[cx + r * np.cos(t0 + d * t), cy + r * np.sin(t0 + d * t)] for t in np.linspace(0, 1, n)])
    return np.concatenate([pts[:a], arc, pts[b:]])


def simplify(pts, tol=0.01):
    """Ramer-Douglas-Peucker on a closed polyline: drop points within tol px of the line through their neighbours."""
    import numpy as np

    def rdp(a):
        if len(a) < 3:
            return a
        d = a[-1] - a[0]
        n = np.hypot(*d) or 1e-9
        dist = np.abs(d[0] * (a[1:-1, 1] - a[0, 1]) - d[1] * (a[1:-1, 0] - a[0, 0])) / n
        i = int(np.argmax(dist)) + 1
        return np.vstack([rdp(a[:i + 1])[:-1], rdp(a[i:])]) if dist[i - 1] > tol else np.vstack([a[0], a[-1]])
    j = len(pts) // 2
    return np.vstack([rdp(np.vstack([pts[:j + 1]]))[:-1], rdp(np.vstack([pts[j:], pts[:1]]))[:-1]])


def poly_d(pts):
    pts = simplify(pts)
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts) + " Z"


def load_project(path=None):
    path = path or os.path.join(ROOT, "projects", "glow", "project.json")
    return json.load(open(path))


def shapes_svg(tuned, photo_edges=0, project=None):
    """Every drawn shape of the project (project.json "drawn", in drawing order), with tuned geometry and colours
    from the tuned-shapes file where present. Kinds: rect, circle, line, squircle (rounded rect with top/bottom
    radii and corner smoothing; "follow" copies another squircle's sides and bottom corners).
    photo_edges > 0: shapes marked "over_photo" are inset by that many px with no border, so their outermost edge
    comes from the photo underneath, and their "subtract" discs are cut out of them (as plain path geometry)."""
    project = project or load_project()
    E = photo_edges
    T = {s["name"]: s for s in tuned if not (s.get("tune") or {}).get("kept")}
    f = lambda v: round(v, 3)
    final = {}  # final geometry of each squircle, for "follow"
    S = []

    def disc(name):
        it = next(d for d in project["drawn"] if d["name"] == name)
        bx, by, bd, _ = T[name]["box"] if name in T else it["box"]
        return bx + bd / 2, by + bd / 2, bd / 2 + 1

    for it in project["drawn"]:
        n, kind = it["name"], it["kind"]
        t = T.get(n)
        if kind == "line":
            x1, y1, x2, y2 = it["points"]
            S.append(f'<line id="{n}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{it["stroke"]}" stroke-width="1"/>')
        elif kind == "rect":
            x, y, w, h = t["box"] if t else it["box"]
            r = t.get("r", it["r"]) if t else it["r"]
            fill = t["fill"] if t else it["fill"]
            stroke = t.get("stroke", it.get("stroke")) if t else it.get("stroke")
            sw = 1
            if E and it.get("over_photo"):
                x, y, w, h, r, stroke = x + E, y + E, w - 2 * E, h - 2 * E, max(r - E, 0), None
            st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
            ins = sw / 2 if stroke else 0  # SVG strokes are centred: inset so the outer edge matches the box
            S.append(f'<rect id="{n}" x="{x + ins}" y="{y + ins}" width="{w - 2 * ins}" height="{h - 2 * ins}" rx="{max(r - ins, 0)}" fill="{fill}"{st}/>')
        elif kind == "circle":
            x, y, d, _ = t["box"] if t else it["box"]
            fill = t["fill"] if t else it["fill"]
            stroke = t.get("stroke", it.get("stroke")) if t else it.get("stroke")
            if E and it.get("over_photo"):
                S.append(f'<circle id="{n}" cx="{x + d / 2}" cy="{y + d / 2}" r="{d / 2 - E}" fill="{fill}"/>')
            elif stroke:
                S.append(f'<circle id="{n}" cx="{x + d / 2}" cy="{y + d / 2}" r="{d / 2 - 0.5}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
            else:  # fill only: no border, so no half-stroke inset
                S.append(f'<circle id="{n}" cx="{x + d / 2}" cy="{y + d / 2}" r="{d / 2}" fill="{fill}"/>')
        elif kind == "squircle":
            sc = {**it, **(t or {})}
            (x0, y0, w0, h0), rt, rb = sc["box"], sc["r"], sc.get("rb", sc["r"])
            k, kb = sc.get("k", 0.5523), sc.get("kb", 0.5523)
            stroke = sc.get("stroke")
            if it.get("follow"):  # same sides and bottom corners as the followed squircle; own top edge
                g = final[it["follow"]]
                x0, x1, y1, rb, kb = g["x0"], g["x1"], g["y1"], g["rb"], g["kb"]
            else:
                if E and it.get("over_photo"):
                    x0, y0, w0, h0, rt, rb, stroke = x0 + E, y0 + E, w0 - 2 * E, h0 - 2 * E, rt - E, rb - E, None
                x1, y1 = x0 + w0, y0 + h0
            final[n] = dict(x0=x0, x1=x1, y1=y1, rb=rb, kb=kb)
            if E and it.get("subtract"):
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from tune_shapes import squircle_points
                pts = squircle_points(x0, y0, x1 - x0, y1 - y0, rt, rb, k, kb, n=48)
                for other in it["subtract"]:
                    pts = minus_disc(pts, *disc(other))
                S.append(f'<path id="{n}" fill="{sc["fill"]}" d="{poly_d(pts)}"/>')
            else:
                bottom = (f"V{f(y1 - rb)} C{f(x1)},{f(y1 - rb + rb * kb)} {f(x1 - rb + rb * kb)},{f(y1)} {f(x1 - rb)},{f(y1)} "
                          f"H{f(x0 + rb)} C{f(x0 + rb - rb * kb)},{f(y1)} {f(x0)},{f(y1 - rb + rb * kb)} {f(x0)},{f(y1 - rb)} ")
                if rt:
                    top = f"M{f(x0 + rt)},{f(y0)} H{f(x1 - rt)} C{f(x1 - rt + rt * k)},{f(y0)} {f(x1)},{f(y0 + rt - rt * k)} {f(x1)},{f(y0 + rt)} "
                    d = f"{top}{bottom}V{f(y0 + rt)} C{f(x0)},{f(y0 + rt - rt * k)} {f(x0 + rt - rt * k)},{f(y0)} {f(x0 + rt)},{f(y0)} Z"
                else:
                    d = f"M{f(x0)},{y0} H{f(x1)} {bottom}V{y0} Z"
                S.append(f'<path id="{n}" fill="{sc["fill"]}" d="{d}"/>')
            if stroke:  # inner border: the outline inset by half the width, stroked
                i = sc.get("sw", 1) / 2
                ix0, iy0, ix1, iy1, irt, irb = x0 + i, y0 + i, x1 - i, y1 - i, rt - i, rb - i
                d = (f"M{f(ix0 + irt)},{f(iy0)} H{f(ix1 - irt)} C{f(ix1 - irt + irt * k)},{f(iy0)} {f(ix1)},{f(iy0 + irt - irt * k)} {f(ix1)},{f(iy0 + irt)} "
                     f"V{f(iy1 - irb)} C{f(ix1)},{f(iy1 - irb + irb * kb)} {f(ix1 - irb + irb * kb)},{f(iy1)} {f(ix1 - irb)},{f(iy1)} "
                     f"H{f(ix0 + irb)} C{f(ix0 + irb - irb * kb)},{f(iy1)} {f(ix0)},{f(iy1 - irb + irb * kb)} {f(ix0)},{f(iy1 - irb)} "
                     f"V{f(iy0 + irt)} C{f(ix0)},{f(iy0 + irt - irt * k)} {f(ix0 + irt - irt * k)},{f(iy0)} {f(ix0 + irt)},{f(iy0)} Z")
                S.append(f'<path id="{n}_edge" fill="none" stroke="{stroke}" stroke-width="{sc.get("sw", 1)}" d="{d}"/>')
    W, H = project["size"]
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "".join(S) + "</svg>"


def main(out, calibration=None, ink=None, rims=True, photo_edges=0, project=None):
    project = project or load_project()
    os.makedirs(out, exist_ok=True)
    p = lambda *a: os.path.join(ROOT, *a)
    W, H = project["size"]
    head = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    o = Image.open(p(project["design"])).convert("RGB")
    plate = Image.open(p(project["plate"])).convert("RGB") if os.path.exists(p(project["plate"])) else None
    tuned = json.load(open(p(project["shapes_tuned"])))
    import numpy as np
    for ph in project["photos"]:  # lossless photo slices
        x, y, w, h = ph["box"]
        im = o.crop((x, y, x + w, y + h))
        # patches inside the slice that belong to something drawn on top (text the slice cuts into) come from the plate
        for px, py, pw, phh in ph.get("patch_from_plate", []):
            if plate is not None:
                im.paste(plate.crop((px, py, px + pw, py + phh)), (px - x, py - y))
        # and, unless photo edges are used, the rims of the shapes drawn over this photo (tools/clean_rims.py)
        if rims and ph["name"] == project.get("photo_under") and project.get("rims"):
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from clean_rims import clean
            arr, _ = clean(np.asarray(im, dtype=np.float64), tuned, x, y, order=project["rims"])
            im = Image.fromarray(np.clip(np.round(arr), 0, 255).astype(np.uint8))
        im.save(os.path.join(out, ph["file"]))
    for st in project.get("strips", []):  # rows/columns shipped as original pixels
        x, y, w, h = st["box"]
        o.crop((x, y, x + w, y + h)).save(os.path.join(out, st["file"]))
    if os.path.exists(p(project["backdrop"])):
        Image.open(p(project["backdrop"])).convert("RGB").resize((W, H), Image.BILINEAR).save(os.path.join(out, "backdrop.png"))
    # full-resolution plate: the original's own background pixels wherever nothing is drawn on top (tools/backdrop.py --plate)
    if plate is not None:
        plate.save(os.path.join(out, "backdrop_plate.png"))
    if calibration:
        cal = json.load(open(calibration))
        for t in tuned:
            c = cal.get(t["name"])
            if c:
                t["box"] = [t["box"][0] + c["dx"], t["box"][1] + c["dy"], t["box"][2] + c["dw"], t["box"][3] + c["dh"]]
                t.setdefault("tune", {})["kept"] = False
    open(os.path.join(out, "shapes_tuned.svg"), "w").write(shapes_svg(tuned, photo_edges, project))
    json.dump(tuned, open(os.path.join(out, "shapes_tuned.json"), "w"), indent=1)  # same geometry as data (the Affinity script reads it)

    rep = {r["name"]: r for r in project.get("repeat", [])}  # elements drawn again elsewhere (card 2 reuses card 1's icons)
    items = []
    for key in ("components", "text"):
        m = p(project["manifests"][key])
        for c in json.load(open(m)):
            items.append((c, os.path.dirname(m)))
            if c["name"] in rep:
                d, dx, dy = copy.deepcopy(c), rep[c["name"]].get("dx", 0), rep[c["name"]].get("dy", 0)
                d["name"] += "_2"
                d["box"][0] += dx; d["box"][1] += dy; d["raster_box"][0] += dx; d["raster_box"][1] += dy
                items.append((d, os.path.dirname(m)))
    vis, hid = [], []
    tiny = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    allc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for c, d in items:
        w = ink.get(c["name"].removesuffix("_2"), 0) if isinstance(ink, dict) else (ink or 0)
        st = f' stroke="{c["colour"]}" stroke-width="{w}" stroke-linejoin="round"' if w else ""
        path = f'<path id="{c["name"]}" fill="{c["colour"]}"{st} transform="translate({c["box"][0]},{c["box"][1]})" d="{c["d"]}"/>'
        (hid if c["mode"] == "raster" else vis).append(path)
        cut = Image.open(os.path.join(d, c["raster"])).convert("RGBA")
        if not c.get("part_of"):  # split-out parts are already inside their parent's full cutout
            allc.alpha_composite(cut, tuple(c["raster_box"][:2]))
        if c["mode"] == "raster":
            tiny.alpha_composite(cut, tuple(c["raster_box"][:2]))
    open(os.path.join(out, "vectors_tuned.svg"), "w").write(head + "".join(vis) + "</svg>")
    open(os.path.join(out, "vectors_tiny_hidden.svg"), "w").write(head + "".join(hid) + "</svg>")
    open(os.path.join(out, "vectors_all.svg"), "w").write(head + "".join(vis + hid) + "</svg>")
    tiny.save(os.path.join(out, "cutouts_tiny.png"))
    allc.save(os.path.join(out, "cutouts_all_max_fidelity.png"))
    print(f"kit written to {out}: {len(vis)} vectors, {len(hid)} tiny elements")

if __name__ == "__main__":
    args = sys.argv[1:]
    cal = args[args.index("--calibration") + 1] if "--calibration" in args else None
    ink = json.load(open(args[args.index("--ink") + 1])) if "--ink" in args else \
        (float(args[args.index("--ink-all") + 1]) if "--ink-all" in args else None)
    pe = float(args[args.index("--photo-edges") + 1]) if "--photo-edges" in args else 0
    proj = load_project(args[args.index("--project") + 1]) if "--project" in args else None
    main(args[0], cal, ink, rims="--no-clean-rims" not in args and not pe, photo_edges=pe, project=proj)
