"""Fit the frosted pills (search field, shipping badge) drawn over the hero photo: a pill (radius h/2) of colour c at
opacity a over the plate. Geometry by coordinate descent to 1/8 px, c and a by least squares for each candidate's
coverage (8x supersampled), text/icon boxes inside excluded. Writes build/pills.json."""
import json
import numpy as np
from PIL import Image, ImageDraw
SS = 8
o = np.asarray(Image.open('design.png').convert('RGB')).astype(float)
p = np.asarray(Image.open('build/plate.png').convert('RGB')).astype(float)

def cov(x, y, w, h, X0, Y0, W, H):
    im = Image.new('L', (W * SS, H * SS), 0)
    r = h / 2
    ImageDraw.Draw(im).rounded_rectangle([(x - X0) * SS, (y - Y0) * SS, (x - X0 + w) * SS - 1, (y - Y0 + h) * SS - 1], r * SS, fill=255)
    return np.asarray(im.resize((W, H), Image.BOX)).astype(float) / 255

def solve(g, X0, Y0, W, H, keep):
    c = cov(*g, X0, Y0, W, H)[keep]
    P = p[Y0:Y0 + H, X0:X0 + W][keep]; O = o[Y0:Y0 + H, X0:X0 + W][keep]
    # o - p = c*(u - a p): unknowns u (3), a (1)
    A = np.zeros((len(c) * 3, 4)); b = (O - P).reshape(-1)
    for ch in range(3):
        A[ch::3, ch] = c; A[ch::3, 3] = -c * P[:, ch]
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    err = ((A @ sol - b) ** 2).mean()
    a = sol[3]; col = sol[:3] / max(a, 1e-6)
    return err, a, col

pills = {"search": ([1132, 18, 272, 45], [(1145, 27, 30, 28), (1176, 31, 145, 20)]),
         "ship": ([83, 171, 324, 37], [(94, 176, 27, 27), (129, 181, 228, 17), (364, 174, 35, 31)])}
out = {}
for name, (g, holes) in pills.items():
    g = [float(v) for v in g]
    X0, Y0, W, H = int(g[0]) - 6, int(g[1]) - 6, int(g[2]) + 12, int(g[3]) + 12
    keep = np.ones((H, W), bool)
    for hx, hy, hw, hh in holes:
        keep[hy - Y0:hy - Y0 + hh, hx - X0:hx - X0 + hw] = False
    best = solve(g, X0, Y0, W, H, keep)[0]
    for step in (1, .5, .25, .125):
        improved = True
        while improved:
            improved = False
            for i in range(4):
                for d in (-step, step):
                    t = list(g); t[i] += d
                    e = solve(t, X0, Y0, W, H, keep)[0]
                    if e < best - 1e-9:
                        best, g, improved = e, t, True
    e, a, col = solve(g, X0, Y0, W, H, keep)
    out[name] = {"box": [round(v, 3) for v in g], "r": round(g[3] / 2, 3), "rgba": [round(v, 1) for v in col] + [round(a, 4)], "rmse": round(e ** .5, 2)}
    print(name, out[name])
json.dump(out, open('build/pills.json', 'w'), indent=1)
