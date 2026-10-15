"""Fit code mode's live text to the design: per element, compare the ink box of the live text (code render minus a
render without text) with the original's (original minus the same bare render), then correct offset, font size
(by ink height) and letter-spacing (by ink width). Run a few rounds: build, render code + bare, fit.
usage: fit_code.py <design.png> <code.png> <bare.png> [--rounds-file code_fit.json]"""
import json, sys, os
import numpy as np
from PIL import Image
D, C, B = (np.asarray(Image.open(f).convert('RGB')).astype(int) for f in sys.argv[1:4])
P = '../../projects/glowseoul/build'
els = json.load(open(f'{P}/text_tuned/manifest.json')) + [c for c in json.load(open(f'{P}/components_tuned/manifest.json')) if c['name'] == 'logo']
TXT = {'logo': 'GlowSeoul'}
FIXED = {'logo', 'tx_head_1', 'tx_head_2', 'tx_head_3'}  # traced fonts: size from glyphfont.py
fit = json.load(open('code_fit.json')) if os.path.exists('code_fit.json') else {}
def ink(img, box, pad=5, thr=40, vpad=2):
    x, y, w, h = box
    sub = np.abs(img[y - vpad:y + h + vpad, x - pad:x + w + pad] - B[y - vpad:y + h + vpad, x - pad:x + w + pad]).sum(2) > thr
    ys, xs = np.where(sub)
    if len(xs) < 5: return None
    return int(xs.min() - pad + x), int(ys.min() - vpad + y), int(xs.max() - pad + x + 1), int(ys.max() - vpad + y + 1)
html = open('src/index.html').read()
import re
for e in els:
    n = e['name']; o = ink(D, e['box']); r = ink(C, e['box'], pad=16, vpad=4)
    if not o or not r: print('skip', n); continue
    f = fit.get(n, {'dx': 0, 'dy': 0, 'k': 1, 'ls': 0})
    oh, rh = o[3] - o[1], r[3] - r[1]; ow, rw = o[2] - o[0], r[2] - r[0]
    m = re.search(r'data-n="%s"[^>]*>(.*?)</' % n, html) ; txt = TXT.get(n) or (re.sub('<[^>]+>|&amp;', 'x', m.group(1)) if m else 'x' * 10)
    nch = max(len(txt) - 1, 1)
    k = oh / rh if rh > 4 else 1
    if abs(k - 1) < 0.004 or n in FIXED: k = 1
    k = min(max(k, 0.95), 1.05)
    f['k'] = round(float(f['k'] * (1 + (k - 1) * 0.8)), 4)
    f['ls'] = round(float(f['ls'] + (ow - rw * k) / nch * 0.8), 3)
    f['dx'] = round(float(f['dx'] + (o[0] - r[0])), 3)
    f['dy'] = round(float(f['dy'] + (o[1] - r[1])), 3)
    fit[n] = f
    print(f'{n:16} orig {o} live {r} -> {f}')
json.dump(fit, open('code_fit.json', 'w'), indent=1)
