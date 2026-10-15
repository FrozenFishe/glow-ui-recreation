"""Web/editor plate for GlowSeoul: the Photoshop clean hero (content-aware fill) over rows 0-814, the original
strip below with the six category cards (drawn as shapes) filled with the strip's own row colour."""
import json, sys
import numpy as np
from PIL import Image
o = np.asarray(Image.open('design.png').convert('RGB')).copy()
ps = np.asarray(Image.open('build/ps_clean_full.png').convert('RGB'))
plate = o.copy()
plate[:815] = ps[:815]
cards = [(83, 339), (355, 608), (624, 862), (878, 1109), (1125, 1352), (1368, 1588)]
m = np.zeros(o.shape[:2], bool)
for x0, x1 in cards:
    m[836:924, x0 - 3:x1 + 4] = True
for y in range(836, 924):
    row = o[y][~m[y]]
    plate[y][m[y]] = np.median(row, axis=0)
Image.fromarray(plate).save('build/plate.png')
print('plate ok; strip row colours', o[830, 40], o[930, 40])
