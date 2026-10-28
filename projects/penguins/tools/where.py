"""Attribute changed pixels (>12% after a 0.7px blur, the benchmark's measure) to shapes and traced elements."""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
o = np.asarray(Image.open('design.png').convert('RGB')).astype(float)
r = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float)
b = lambda a: ndi.gaussian_filter(a, (0.7, 0.7, 0))
d = np.abs(b(o) - b(r)).max(2) > 0.12 * 255
boxes = [(s['name'], s['box']) for s in json.load(open('build/shapes_tuned.json'))]
for f in ['build/components_tuned/manifest.json', 'build/text_tuned/manifest.json']:
    boxes += [(e['name'], e['box']) for e in json.load(open(f))]
used = np.zeros_like(d); res = []
for n, (x, y, w, h) in boxes:
    x0, y0, x1, y1 = int(x) - 3, int(y) - 3, int(x + w) + 4, int(y + h) + 4
    m = d[y0:y1, x0:x1] & ~used[y0:y1, x0:x1]; res.append((int(m.sum()), n)); used[y0:y1, x0:x1] = True
res.sort(reverse=True)
print('changed', int(d.sum()), res[:int(sys.argv[2]) if len(sys.argv) > 2 else 10], 'outside', int((d & ~used).sum()))
