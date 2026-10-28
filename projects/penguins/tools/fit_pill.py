"""Fit the hero's outline button: a pill of colour c at opacity a, a semi-transparent ring (colour, opacity, width)
and a soft dark shadow (Gaussian of the pill, opacity s), over the plate. Geometry and blur by grid search to 1/4 px; c, a, s by least squares on the
original (the traced label's pixels excluded: it is drawn on top). Writes build/pill.json and build/pill.png."""
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
SS = 8
o = np.asarray(Image.open('design.png').convert('RGB')).astype(float)
p = np.asarray(Image.open('build/plate.png').convert('RGB')).astype(float)
X0, Y0, W, H = 236, 356, 180, 84
O, P = o[Y0:Y0 + H, X0:X0 + W], p[Y0:Y0 + H, X0:X0 + W]
ring = [e for e in json.load(open('build/text_tuned/manifest.json')) if e['name'] == 'tx_btn2']
ex = np.zeros((H, W), bool)
for e in ring:
    a = np.asarray(Image.open('build/text_tuned/%s-raster.png' % e['name']).split()[-1]) > 90
    x, y, w, h = e['raster_box']
    if a is not None and a.shape == (h, w):
        ex[y - Y0:y - Y0 + h, x - X0:x - X0 + w] |= a
ex = ndi.binary_dilation(ex, iterations=1)
# the white button's edge sits on the left of the window
ex[:, :241 - X0] = True
keep = ~ex

def cov(x, y, w, h):
    im = Image.new('L', (W * SS, H * SS), 0)
    ImageDraw.Draw(im).rounded_rectangle([(x - X0) * SS, (y - Y0) * SS, (x - X0 + w) * SS - 1, (y - Y0 + h) * SS - 1], h / 2 * SS, fill=255)
    return np.asarray(im.resize((W, H), Image.BOX)).astype(float) / 255

SW = 1.0

def ringcov(x, y, w, h):
    return np.clip(cov(x, y, w, h) - cov(x + SW, y + SW, w - 2 * SW, h - 2 * SW), 0, 1)

def solve(g, sig):
    c = cov(*g); sh = ndi.gaussian_filter(c, sig) if sig else np.zeros_like(c); rc = ringcov(*g)
    cc, ss, rr, PP, OO = c[keep], sh[keep], rc[keep], P[keep], O[keep]
    # o - p = c*u - a*c*p - s*sh*p + a2*rc*(255 - p)   (u = a*colour; the ring is white): u(3), a, s, a2
    A = np.zeros((len(cc) * 3, 6)); b = (OO - PP).reshape(-1)
    for ch in range(3):
        A[ch::3, ch] = cc; A[ch::3, 3] = -cc * PP[:, ch]; A[ch::3, 4] = -ss * PP[:, ch]; A[ch::3, 5] = rr * (255 - PP[:, ch])
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    return ((A @ sol - b) ** 2).mean(), sol

best = None
g = [254.5, 374.5, 141.0, 45.5]
for sig in (3, 4, 6, 8):
    for step in (1, 0.5, 0.25):
        improved = True
        while improved:
            improved = False
            for k in range(4):
                for dv in (-step, step):
                    t = list(g); t[k] += dv
                    e, sol = solve(t, sig)
                    if best is None or e < best[0]:
                        best, g, improved = (e, sol, list(t), sig), t, True
    g = list(best[2])
for sw in (0.75, 1.25, 1.5):
    SW0, SW = SW, sw
    e2, sol2 = solve(best[2], best[3])
    if e2 < best[0]: best = (e2, sol2, best[2], best[3])
    else: SW = SW0
e, sol, g, sig = best
a2 = sol[5]; rcol = np.array([255.0, 255.0, 255.0])
print('ring width %s colour %s opacity %.3f' % (SW, np.round(rcol), a2))
a, s = sol[3], sol[4]; col = sol[:3] / max(a, 1e-6)
print('err %.2f  box %s  sigma %s  colour %s  opacity %.3f  shadow %.3f' % (e, g, sig, np.round(col), a, s))
# baseline error (plate only)
print('plate-only err %.2f' % (((O - P)[keep]) ** 2).mean())
c = cov(*g); sh = ndi.gaussian_filter(c, sig) if sig else np.zeros_like(c)
# RGBA layer: composite = p*(1 - a c - s sh) + a c col  ->  alpha = a c + s sh, rgb = a c col / alpha
A = np.clip(a * c + s * sh, 0, 1); rgb = (a * c)[..., None] * col / np.maximum(A, 1e-6)[..., None]
rc = ringcov(*g); A2 = np.clip(a2 * rc, 0, 1)  # ring layer composited over the fill layer
Ao = A2 + A * (1 - A2)
rgb = (rcol * A2[..., None] + rgb * (A * (1 - A2))[..., None]) / np.maximum(Ao, 1e-6)[..., None]; A = Ao
full = np.zeros((o.shape[0], o.shape[1], 4))
full[Y0:Y0 + H, X0:X0 + W, :3] = rgb; full[Y0:Y0 + H, X0:X0 + W, 3] = A * 255
Image.fromarray(np.clip(np.round(full), 0, 255).astype(np.uint8)).save('build/pill.png')
json.dump({'box': g, 'r': g[3] / 2, 'colour': '#%02X%02X%02X' % tuple(int(round(v)) for v in np.clip(col, 0, 255)),
           'opacity': round(float(a), 4), 'shadow_opacity': round(float(s), 4), 'shadow_sigma': sig, 'ring': {'width': SW, 'colour': '#%02X%02X%02X' % tuple(int(round(v)) for v in np.clip(rcol, 0, 255)), 'opacity': round(float(a2), 4)}}, open('build/pill.json', 'w'), indent=1)
