"""Plate for the penguins page: the original where nothing is drawn; under drawn UI, Photoshop's content-aware
fill inside the photo areas (hero, impact banner) and a normalised-convolution fill of the surrounding
background on the flat white sections (content-aware fill leaves faint smudges there) and under the hero copy."""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
o = np.asarray(Image.open('design.png').convert('RGB')).astype(float)
ps = np.asarray(Image.open('build/ps_clean_full.png').convert('RGB')).astype(float)
m = np.asarray(Image.open('build/ui_mask.png')) > 0
H, W = m.shape
photo = np.zeros_like(m)
for x, y, w, h in [(0, 55, 1214, 477), (27, 873, 1160, 198), (81, 1105, 467, 190)]:
    photo[y:y + h, x:x + w] = True
# the hero copy sits on the soft, out-of-focus part of the photo: a smooth fill from the surrounding pixels
# matches it better than content-aware fill, which brightened the area under the buttons
soft = np.zeros_like(m); soft[120:430, 80:480] = True
plate = o.copy()
plate[m & photo & ~soft] = ps[m & photo & ~soft]
flat = m & (~photo | soft)
k = (~m).astype(float)
for s in (2, 4, 8, 16):
    num = np.stack([ndi.gaussian_filter(o[..., c] * k, s) for c in range(3)], -1)
    den = ndi.gaussian_filter(k, s)[..., None]
    fill = num / np.maximum(den, 1e-6)
    ok = flat & (den[..., 0] > 0.05)
    plate[ok] = fill[ok]; flat &= ~ok
Image.fromarray(np.clip(np.round(plate), 0, 255).astype(np.uint8)).save('build/plate.png')
print('plate ok, unfilled', int(flat.sum()))
