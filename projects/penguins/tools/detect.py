"""Find foreground blobs (text lines, icons, shapes) in regions of the penguins design: difference from a
31px median background, horizontal dilation to join a line's letters, connected components -> boxes."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
o = np.asarray(Image.open('design.png').convert('RGB')).astype(np.float32)
import os
if os.path.exists('build/diff.npy'):
    d = np.load('build/diff.npy')
else:
    bg = ndi.median_filter(o, size=(31, 31, 1))
    d = np.abs(o - bg).sum(2)
    np.save('build/diff.npy', d)
x0, y0, x1, y1, thr, gap = [int(v) for v in sys.argv[1:7]]
m = d[y0:y1, x0:x1] > thr
mm = ndi.binary_dilation(m, structure=np.ones((3, gap)))
lab, n = ndi.label(mm)
for sl in ndi.find_objects(lab):
    sub = m[sl]
    if sub.sum() < 6: continue
    ys, xs = np.nonzero(sub)
    print([x0 + sl[1].start + xs.min(), y0 + sl[0].start + ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1], int(sub.sum()))
