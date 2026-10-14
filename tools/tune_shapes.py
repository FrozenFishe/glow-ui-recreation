"""Auto-tune drawn shapes (rounded rectangles, circles) against the original.

For each shape in a spec it searches the geometry (x, y, w, h, corner radius,
in steps down to 1/8 px by coordinate descent) and solves the fill and border
colours by least squares for each candidate's coverage, scoring a simulated
render (8x supersampled) against the original pixels around the shape's edge
and inside it. Pixels covered by traced elements drawn on top (text, icons)
are excluded from the score.

With --under, the score composites each candidate over that image (what the rebuild actually draws the
shapes on: the backdrop plate plus the rim-cleaned hero slice, see tools/clean_rims.py) instead of guessing the
background from the shape's surroundings. That matters for shapes over a photo, such as the trusted badge.
--stroke-widths also searches the border width.

usage: tune_shapes.py <design> <shapes.json> <out.json> --exclude manifest.json [--exclude ...]
                      [--under under.png] [--stroke-widths 0.75,1,1.25,1.5] [--only name,name]
"""
import argparse
import json

import numpy as np
from PIL import Image, ImageDraw

SS = 8
PAD = 5


def hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def rgb2hex(c):
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in np.clip(c, 0, 255))


def squircle_points(x, y, w, h, r, rb, k, kb, n=24):
    """Outline of a rounded rectangle with top radius r, bottom radius rb and corner smoothing k / kb.
    Each corner is one cubic Bezier from the edge to the edge; k = 0.5523 is a circular arc, larger k gives the
    flatter, continuous ("squircle") corner of iOS screens and icons. Matches the SVG path make_kit.py writes."""
    def corner(p0, c0, c1, p1):
        t = np.linspace(0, 1, n)[:, None]
        return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c0 + 3 * (1 - t) * t ** 2 * c1 + t ** 3 * p1
    A = np.array
    x1, y1 = x + w, y + h
    pts = [corner(A([x1 - r, y]), A([x1 - r + r * k, y]), A([x1, y + r - r * k]), A([x1, y + r])),
           corner(A([x1, y1 - rb]), A([x1, y1 - rb + rb * kb]), A([x1 - rb + rb * kb, y1]), A([x1 - rb, y1])),
           corner(A([x + rb, y1]), A([x + rb - rb * kb, y1]), A([x, y1 - rb + rb * kb]), A([x, y1 - rb])),
           corner(A([x, y + r]), A([x, y + r - r * k]), A([x + r - r * k, y]), A([x + r, y]))]
    return np.concatenate(pts)


def masks(kind, x, y, w, h, r, sw, X0, Y0, RW, RH, extra=None):
    """Coverage of the whole shape (outer) and of its fill area inside the border (inner), at 1x."""
    def draw(inset):
        im = Image.new("L", (RW * SS, RH * SS), 0)
        d = ImageDraw.Draw(im)
        bx0, by0 = (x - X0 + inset) * SS, (y - Y0 + inset) * SS
        bx1, by1 = (x - X0 + w - inset) * SS, (y - Y0 + h - inset) * SS
        if bx1 <= bx0 or by1 <= by0:
            return np.zeros((RH, RW))
        if kind == "squircle":
            rb, k, kb = extra
            pts = squircle_points(x + inset, y + inset, w - 2 * inset, h - 2 * inset, max(r - inset, 0), max(rb - inset, 0), k, kb)
            d.polygon([((px - X0) * SS, (py - Y0) * SS) for px, py in pts], fill=255)
        elif kind == "circle":
            d.ellipse([bx0, by0, bx1, by1], fill=255)
        else:
            d.rounded_rectangle([bx0, by0, bx1, by1], radius=max(r - inset, 0) * SS, fill=255)
        a = np.asarray(im, dtype=np.float64) / 255.0
        return a.reshape(RH, SS, RW, SS).mean(axis=(1, 3))
    outer = draw(0)
    inner = draw(sw) if sw else outer
    return outer, inner


def fit(outer, inner, orig, under, valid, has_stroke):
    """Least-squares fill (and border) colours for this coverage; returns colours and mean abs error."""
    border = outer - inner
    target = orig - under * (1 - outer)[..., None]
    v = valid & (outer > 0.002)
    if v.sum() < 4:
        return None, None, 1e9
    if has_stroke and border[v].sum() > 1:
        A = np.stack([inner[v], border[v]], axis=1)
        sol, *_ = np.linalg.lstsq(A, target[v], rcond=None)
        fill, stroke = sol[0], sol[1]
    else:
        fill = (inner[v][:, None] * target[v]).sum(0) / max((inner[v] ** 2).sum(), 1e-9)
        stroke = None
    fill = np.clip(fill, 0, 255)
    stroke = np.clip(stroke, 0, 255) if stroke is not None else None
    comp = under * (1 - outer)[..., None] + fill * inner[..., None] + (stroke * border[..., None] if stroke is not None else 0)
    err = float(np.abs(comp - orig)[valid].mean())
    return fill, stroke, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("shapes")
    ap.add_argument("out")
    ap.add_argument("--exclude", action="append", default=[], help="manifest(s) of traced elements drawn on top")
    ap.add_argument("--exclude-box", action="append", default=[], help="x,y,w,h of other content on top (photos)")
    ap.add_argument("--max-move", type=float, default=3.0, help="largest change to any geometry value, px")
    ap.add_argument("--under", help="full-canvas image the shapes are drawn over (instead of estimating it)")
    ap.add_argument("--stroke-widths", help="comma-separated border widths to try for shapes with a border")
    ap.add_argument("--only", help="comma-separated shape names to tune (others are copied unchanged)")
    ap.add_argument("--edge-band", type=int, help="score only pixels within this many px of the outline (large shapes whose interior holds other content)")
    a = ap.parse_args()
    img = np.asarray(Image.open(a.design).convert("RGB"), dtype=np.float64)
    H, W = img.shape[:2]
    covered = np.zeros((H, W), bool)
    for m in a.exclude:
        for c in json.load(open(m)):
            x, y, w, h = c.get("raster_box") or c["box"]
            covered[y:y + h, x:x + w] = True
    for b in a.exclude_box:
        x, y, w, h = map(int, b.split(","))
        covered[y:y + h, x:x + w] = True
    shapes = json.load(open(a.shapes))
    UNDER = np.asarray(Image.open(a.under).convert("RGB"), dtype=np.float64) if a.under else None
    only = set(a.only.split(",")) if a.only else None

    out = []
    for s in shapes:
        if only and s["name"] not in only:
            out.append(s)
            continue
        x, y, w, h = s["box"]
        r, sw, kind = s.get("r", 0), s.get("sw", 0), s["kind"]
        X0, Y0 = int(np.floor(x)) - PAD, int(np.floor(y)) - PAD
        X1, Y1 = int(np.ceil(x + w)) + PAD, int(np.ceil(y + h)) + PAD
        X0, Y0, X1, Y1 = max(X0, 0), max(Y0, 0), min(X1, W), min(Y1, H)
        RW, RH = X1 - X0, Y1 - Y0
        orig = img[Y0:Y1, X0:X1]
        valid = ~covered[Y0:Y1, X0:X1]
        # shapes nested inside this one (a button in a bar) are drawn on top: exclude them too
        for t in shapes:
            if t is s:
                continue
            tx, ty, tw, th = t["box"]
            if tx >= x - 1 and ty >= y - 1 and tx + tw <= x + w + 1 and ty + th <= y + h + 1 and tw * th < w * h:
                gx0, gy0 = int(np.floor(tx)) - 2 - X0, int(np.floor(ty)) - 2 - Y0
                valid[max(gy0, 0):int(np.ceil(ty + th)) + 2 - Y0, max(gx0, 0):int(np.ceil(tx + tw)) + 2 - X0] = False
        # what lies under the shape: outside it, the original itself; at and inside its edge, the median just outside
        ring = np.ones((RH, RW), bool)
        ring[PAD - 1:RH - PAD + 1, PAD - 1:RW - PAD + 1] = False
        ring_med = np.median(orig[ring & valid], axis=0) if (ring & valid).any() else np.median(orig.reshape(-1, 3), axis=0)
        o_init, _ = masks(kind, x, y, w, h, r, sw, X0, Y0, RW, RH,
                          (s.get("rb", r), s.get("k", 0.5523), s.get("kb", 0.5523)) if kind == "squircle" else None)
        from PIL import ImageFilter
        grow = np.asarray(Image.fromarray((o_init > 0).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
        if a.edge_band:
            b = Image.fromarray((o_init > 0.5).astype(np.uint8) * 255)
            n = 2 * a.edge_band + 1
            valid &= (np.asarray(b.filter(ImageFilter.MaxFilter(n))) > 0) & ~(np.asarray(b.filter(ImageFilter.MinFilter(n))) > 0)
        if UNDER is None:
            under = np.where(grow[..., None], ring_med, orig)
        else:  # the real background, plus every shape that encloses this one (a card under its Book button)
            under = UNDER[Y0:Y1, X0:X1].copy()
            for t in shapes:
                tx, ty, tw, th = t["box"]
                if t is s or not (tx <= x + 1 and ty <= y + 1 and tx + tw >= x + w - 1 and ty + th >= y + h - 1 and tw * th > w * h):
                    continue
                tsw = t.get("sw", 0) if t.get("stroke") else 0
                to, ti = masks(t["kind"], tx, ty, tw, th, t.get("r", 0), tsw, X0, Y0, RW, RH,
                               (t.get("rb", t.get("r", 0)), t.get("k", 0.5523), t.get("kb", 0.5523)) if t["kind"] == "squircle" else None)
                under = under * (1 - to)[..., None] + hex2rgb(t["fill"]) * ti[..., None] + (hex2rgb(t["stroke"]) * (to - ti)[..., None] if tsw else 0)

        sq = kind == "squircle"
        ex = lambda q: (q[5], q[6], q[7]) if sq else None

        def score(p):
            o, i = masks(kind, p[0], p[1], p[2], p[3], p[4], sw, X0, Y0, RW, RH, ex(p))
            return fit(o, i, orig, under, valid, bool(sw))

        p = [x, y, w, h, r] + ([s.get("rb", r), s.get("k", 0.5523), s.get("kb", 0.5523)] if sq else [])
        fill0, stroke0 = hex2rgb(s["fill"]), hex2rgb(s["stroke"]) if s.get("stroke") else None
        o, i = masks(kind, *p[:5], sw, X0, Y0, RW, RH, ex(p))
        comp0 = under * (1 - o)[..., None] + fill0 * i[..., None] + (stroke0 * (o - i)[..., None] if stroke0 is not None else 0)
        start = list(p)
        scale = [1, 1, 1, 1, 1] + ([1, 0.04, 0.04] if sq else [])  # smoothing moves in steps of 0.04 x the px step
        e_before = float(np.abs(comp0 - orig)[valid].mean())

        best = score(p)
        for step in (1.0, 0.5, 0.25, 0.125):
            improved = True
            while improved:
                improved = False
                for k in range(len(p) if kind != "circle" else 4):
                    for sgn in (-1, 1):
                        q = list(p)
                        q[k] += sgn * step * scale[k]
                        if kind == "circle" and k in (2, 3):  # keep circles round
                            q[2] = q[3] = q[k]
                        if q[2] <= 1 or q[3] <= 1 or q[4] < 0 or abs(q[k] - start[k]) > a.max_move * scale[k] * (10 if sq and k >= 6 else 1):
                            continue
                        res = score(q)
                        if res[2] < best[2] - 1e-6:
                            best, p, improved = res, q, True
        if sw and a.stroke_widths:  # then the border width, at the best geometry
            for cand in map(float, a.stroke_widths.split(",")):
                o, i = masks(kind, *p[:5], cand, X0, Y0, RW, RH, ex(p))
                res = fit(o, i, orig, under, valid, True)
                if res[2] < best[2] - 1e-6:
                    best, sw = res, cand
        fill, stroke, e_after = best
        rec = dict(s)
        if e_after >= e_before:  # never accept a worse result: keep the measured values
            rec["tune"] = {"err_before": round(e_before, 3), "err_after": round(e_before, 3), "kept": True}
            out.append(rec)
            print(f'{s["name"]:16} err {e_before:6.2f} (kept: tuning did not improve it)')
            continue
        if sq:
            rec.update(rb=round(p[5], 3), k=round(p[6], 4), kb=round(p[7], 4))
        rec.update(box=[round(v, 3) for v in p[:4]], r=round(p[4], 3), fill=rgb2hex(fill),
                   tune={"err_before": round(e_before, 3), "err_after": round(e_after, 3)})
        if stroke is not None:
            rec["stroke"] = rgb2hex(stroke)
            rec["sw"] = sw
        out.append(rec)
        print(f'{s["name"]:16} err {e_before:6.2f} -> {e_after:6.2f}  box {rec["box"]} r {rec["r"]} fill {rec["fill"]}' + (f' stroke {rec["stroke"]}' if stroke is not None else ""))
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
