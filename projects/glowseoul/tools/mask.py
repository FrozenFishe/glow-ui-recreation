"""Mask of the UI drawn over the GlowSeoul hero photo (text, pills, button, icons).
Writes build/ui_mask.png (white = remove) for Photoshop's content-aware fill."""
import sys, json
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

src, out = sys.argv[1], sys.argv[2]
a = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
H, W, _ = a.shape
bg = ndi.median_filter(a, size=(31, 31, 1))
d = np.abs(a - bg).sum(2)
m = np.zeros((H, W), bool)
# areas where UI sits over the photo
regions = [(60, 10, 960, 72), (1120, 8, 1615, 72), (75, 228, 600, 442), (75, 455, 512, 540), (80, 660, 550, 704)]
for x0, y0, x1, y1 in regions:
    m[y0:y1, x0:x1] |= d[y0:y1, x0:x1] > 28

def rrect(x, y, w, h, r):
    yy, xx = np.mgrid[0:H, 0:W]
    cx = np.clip(xx, x + r, x + w - r); cy = np.clip(yy, y + r, y + h - r)
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r

shapes = json.load(open(sys.argv[3]))
for s in shapes:
    m |= rrect(*s)
m = ndi.binary_dilation(m, iterations=4)
Image.fromarray((m * 255).astype(np.uint8)).save(out)
print('masked px', int(m.sum()))
