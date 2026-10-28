"""Mask of everything drawn on the penguins page (traced elements + drawn shapes), white = remove.
Writes build/ui_mask.png for Photoshop's content-aware fill (editors/photoshop/slice.jsx)."""
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
o = Image.open('design.png').convert('RGB'); W, H = o.size
m = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(m)
d = np.load('build/diff.npy')
ink = np.zeros((H, W), bool)
for f in ['build/components_tuned/manifest.json', 'build/text_tuned/manifest.json']:
    for e in json.load(open(f)):
        x, y, w, h = e['box']
        ink[y - 1:y + h + 1, x - 1:x + w + 1] |= d[y - 1:y + h + 1, x - 1:x + w + 1] > 25
for s in json.load(open('specs/shapes.json')):
    if s['kind'] == 'line':
        x0, y0, x1, y1 = s['points']; dr.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill=255)
    else:
        x, y, w, h = s['box']; r = w / 2 if s['kind'] == 'circle' else s.get('r', 0)
        dr.rounded_rectangle([x - 2, y - 2, x + w + 2, y + h + 2], r + 2, fill=255)
# outline pill over the hero photo
dr.rounded_rectangle([251, 371, 398, 423], 26, fill=255)
mm = np.asarray(m) > 0 | ndi.binary_dilation(ink, iterations=3)
mm = (np.asarray(m) > 0) | ndi.binary_dilation(ink, iterations=3)
Image.fromarray((mm * 255).astype(np.uint8)).save('build/ui_mask.png')
print('masked px', int(mm.sum()))
