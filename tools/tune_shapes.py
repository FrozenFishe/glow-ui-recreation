"""Auto-tune drawn shapes (rounded rectangles, circles) against the original.

For each shape in a spec it searches the geometry (x, y, w, h, corner radius,
in steps down to 1/8 px by coordinate descent) and solves the fill and border
colours by least squares for each candidate's coverage, scoring a simulated
render (8x supersampled) against the original pixels around the shape's edge
and inside it. Pixels covered by traced elements drawn on top (text, icons)
are excluded from the score.

usage: tune_shapes.py <design> <shapes.json> <out.json> --exclude manifest.json [--exclude ...]
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


def masks(kind, x, y, w, h, r, sw, X0, Y0, RW, RH):
    """Coverage of the whole shape (outer) and of its fill area inside the border (inner), at 1x."""
    def draw(inset):
        im = Image.new("L", (RW * SS, RH * SS), 0)
        d = ImageDraw.Draw(im)
        bx0, by0 = (x - X0 + inset) * SS, (y - Y0 + inset) * SS
        bx1, by1 = (x - X0 + w - inset) * SS, (y - Y0 + h - inset) * SS
        if bx1 <= bx0 or by1 <= by0:
            return np.zeros((RH, RW))
        if kind == "circle":
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

    out = []
    for s in shapes:
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
        o_init, _ = masks(kind, x, y, w, h, r, sw, X0, Y0, RW, RH)
        grow = np.asarray(Image.fromarray((o_init > 0).astype(np.uint8) * 255).filter(__import__("PIL.ImageFilter", fromlist=["x"]).MaxFilter(5))) > 0
        under = np.where(grow[..., None], ring_med, orig)

        def score(p):
            o, i = masks(kind, p[0], p[1], p[2], p[3], p[4], sw, X0, Y0, RW, RH)
            return fit(o, i, orig, under, valid, bool(sw))

        p = [x, y, w, h, r]
        fill0, stroke0 = hex2rgb(s["fill"]), hex2rgb(s["stroke"]) if s.get("stroke") else None
        o, i = masks(kind, *p, sw, X0, Y0, RW, RH)
        comp0 = under * (1 - o)[..., None] + fill0 * i[..., None] + (stroke0 * (o - i)[..., None] if stroke0 is not None else 0)
        start = [x, y, w, h, r]
        e_before = float(np.abs(comp0 - orig)[valid].mean())

        best = score(p)
        for step in (1.0, 0.5, 0.25, 0.125):
            improved = True
            while improved:
                improved = False
                for k in range(5 if kind == "rect" else 4):
                    for sgn in (-1, 1):
                        q = list(p)
                        q[k] += sgn * step
                        if kind == "circle" and k in (2, 3):  # keep circles round
                            q[2] = q[3] = q[k]
                        if q[2] <= 1 or q[3] <= 1 or q[4] < 0 or abs(q[k] - start[k]) > a.max_move:
                            continue
                        res = score(q)
                        if res[2] < best[2] - 1e-6:
                            best, p, improved = res, q, True
        fill, stroke, e_after = best
        rec = dict(s)
        if e_after >= e_before:  # never accept a worse result: keep the measured values
            rec["tune"] = {"err_before": round(e_before, 3), "err_after": round(e_before, 3), "kept": True}
            out.append(rec)
            print(f'{s["name"]:16} err {e_before:6.2f} (kept: tuning did not improve it)')
            continue
        rec.update(box=[round(v, 3) for v in p[:4]], r=round(p[4], 3), fill=rgb2hex(fill),
                   tune={"err_before": round(e_before, 3), "err_after": round(e_after, 3)})
        if stroke is not None:
            rec["stroke"] = rgb2hex(stroke)
        out.append(rec)
        print(f'{s["name"]:16} err {e_before:6.2f} -> {e_after:6.2f}  box {rec["box"]} r {rec["r"]} fill {rec["fill"]}' + (f' stroke {rec["stroke"]}' if stroke is not None else ""))
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
