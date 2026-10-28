"""Trace multi-tone marks (the logo, the tinted icons) as layered vectors: k-means finds the mark's tones, every
pixel of an 8x Lanczos upscale is assigned to its nearest tone (or the background), and each tone is traced with
potrace (fills opened to drop anti-aliasing rings, then grown under the outline; the outline on top).
Writes build/tones/<name>.svg (viewBox = the design box) and build/tones/manifest.json."""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools'))
from slicer import parse_potrace_svg, path_d
from scipy.cluster.vq import kmeans2
UP = 8
o = Image.open('design.png').convert('RGB')
ITEMS = [  # name, box, number of ink tones
    ('logo', [82, 7, 31, 39], 3), ('ic_penguin', [180, 692, 36, 44], 1), ('ic_leaf', [456, 694, 36, 40], 2),
    ('ic_people', [724, 696, 40, 34], 2), ('ic_cap', [999, 696, 42, 34], 1), ('st_penguin', [89, 993, 36, 42], 1),
    ('st_leaf', [273, 997, 30, 33], 2), ('st_people', [450, 998, 33, 30], 2), ('st_heart', [632, 999, 33, 30], 2),
    ('hero_heart', [115, 389, 19, 17], 2), ('nav_heart', [961, 19, 16, 16], 1), ('story_arrow', [725, 1258, 15, 13], 1),
    ('lang_chev', [1120, 23, 12, 9], 1)]
out = []
for name, (x, y, w, h), k in ITEMS:
    rgb = np.asarray(o.crop((x, y, x + w, y + h))).astype(float)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, 0)
    d = np.abs(rgb - bg).sum(2)
    ink = rgb[d > 60].reshape(-1, 3)
    np.random.seed(1)
    cent, _ = kmeans2(ink, k, minit='++', seed=1) if k > 1 else (ink.mean(0, keepdims=True), None)
    # order by distance from the background: farthest = darkest, traced last (on top)
    cent = sorted(cent, key=lambda c: np.abs(c - bg).sum())
    # colour of each tone: the darkest from its stroke core (30% of its pixels farthest from the background),
    # lighter fills from their median
    lab0 = ((ink[:, None, :] - np.stack(cent)[None]) ** 2).sum(2).argmin(1)
    core = []
    for i, c in enumerate(cent):
        px = ink[lab0 == i]
        far = np.abs(px - bg).sum(1)
        last = i == len(cent) - 1  # outlines: stroke core; lighter fills: their median
        core.append((px[far >= np.percentile(far, 70)].mean(0) if last else np.median(px, 0)) if len(px) > 3 else c)
    fills = core
    big = np.asarray(Image.fromarray(rgb.astype(np.uint8)).resize((w * UP, h * UP), Image.LANCZOS)).astype(float)
    classes = np.stack([bg] + list(cent))
    dist = ((big[:, :, None, :] - classes[None, None]) ** 2).sum(3)
    lab = dist.argmin(2)
    layers = []
    for i, c in enumerate(fills, start=1):
        if i == len(fills):
            mask = lab >= i
        else:  # a fill: drop thin anti-aliasing rings (opening), then grow it under the outline that covers its edge
            from scipy import ndimage as ndi
            disk = lambda r: np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r
            mask = ndi.binary_opening(lab == i, structure=disk(UP))
            mask = ndi.binary_dilation(mask, structure=disk(UP)) & ndi.binary_fill_holes(lab >= 1)
        with tempfile.TemporaryDirectory() as tmp:
            pbm, svg = os.path.join(tmp, 'in.pbm'), os.path.join(tmp, 'out.svg')
            Image.fromarray(~mask).convert('1').save(pbm)
            subprocess.run(['potrace', '-s', '--turdsize', '6', '--alphamax', '1.0', '--opttolerance', '0.2', '-o', svg, pbm], check=True)
            sub = parse_potrace_svg(open(svg).read())[0]
        # potrace pixel space -> design px within the box
        sub = [[[s[0]] + [v / UP for v in s[1:]] for s in sp] for sp in sub]
        hexc = '#%02X%02X%02X' % tuple(int(round(v)) for v in c)
        layers.append({'fill': hexc, 'd': path_d(sub)})
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">' + ''.join(
        f'<path fill="{l["fill"]}" fill-rule="evenodd" d="{l["d"]}"/>' for l in layers) + '</svg>'
    open(f'build/tones/{name}.svg', 'w').write(svg)
    out.append({'name': name, 'box': [x, y, w, h], 'layers': layers})
    print(name, [l['fill'] for l in layers], len(svg))
json.dump(out, open('build/tones/manifest.json', 'w'), indent=1)
