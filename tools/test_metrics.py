"""Tests for the image metrics every benchmark number in the README is computed with.

Covers the pure functions in benchmark.py (changed %, SSIM, CIEDE2000, PSNR, JPEG
quality estimation) and the shift search in diffcheck.py, against known reference
values (Sharma et al. 2005 for CIEDE2000, closed-form values for the rest).

Run:  tools/.venv/bin/python tools/test_metrics.py
No test framework needed; exits non-zero on the first failure.
"""
import io
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark
import diffcheck


def _img(arr):
    return Image.fromarray(arr.astype(np.uint8))


def test_psnr():
    a = np.full((16, 16, 3), 100, np.uint8)
    assert benchmark.psnr(a, a) == float("inf")
    # one channel off by 15 on every pixel: mse = 15^2 / 3
    b = a.copy()
    b[..., 0] = 115
    assert abs(benchmark.psnr(a, b) - 10 * np.log10(255**2 / (225 / 3))) < 1e-9


def test_changed_pct():
    a = np.full((32, 32, 3), 100, np.uint8)
    assert benchmark.changed_pct(_img(a), _img(a)) == 0.0
    # right half off by 40%: flat areas, so the 0.7px blur doesn't smear the boundary much
    b = a.copy()
    b[:, 16:] = 140
    v = benchmark.changed_pct(_img(a), _img(b))
    assert 45 < v < 55, v


def test_ssim():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 256, (32, 32, 3)).astype(np.uint8)
    assert abs(benchmark.ssim(_img(a), _img(a)) - 1.0) < 1e-9
    # smooth image vs itself shifted: high but below 1
    x = np.linspace(0, 255, 32)
    a = np.stack([x[None, :] * np.ones((32, 1))] * 3, axis=2).astype(np.uint8)
    b = np.roll(a, 2, axis=1)
    v = benchmark.ssim(_img(a), _img(b))
    assert 0.8 < v < 1.0, v


def test_to_lab():
    lab = benchmark.to_lab(_img(np.full((4, 4, 3), 255, np.uint8)))
    assert np.allclose(lab, [100, 0, 0], atol=1e-6)
    lab = benchmark.to_lab(_img(np.zeros((4, 4, 3), np.uint8)))
    assert np.allclose(lab, [0, 0, 0], atol=1e-6)
    # sRGB mid grey -> L ~= 53.59, a = b = 0
    lab = benchmark.to_lab(_img(np.full((4, 4, 3), 128, np.uint8)))
    assert abs(lab[0][0, 0] - 53.586) < 0.01, lab[0][0, 0]
    assert abs(lab[1][0, 0]) < 1e-6 and abs(lab[2][0, 0]) < 1e-6


def test_ciede2000():
    # Sharma et al. (2005) validation dataset, first pairs of Table 1
    cases = [
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 2.5, 0.0), (50.0, 0.0, 0.0), 2.4911),
        ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.5144),
        ((50.0, 2.6772, -79.7751), (50.0, 0.0426, -82.7485), 2.3465),
        ((50.0, 2.6772, -79.7751), (50.0, 0.0626, -82.7485), 2.2289),
    ]
    for l1, l2, want in cases:
        got = float(benchmark.ciede2000(l1, l2))
        assert abs(got - want) < 1e-3, (l1, l2, got, want)
    # identical colours: exactly 0
    assert float(benchmark.ciede2000((60.0, 10.0, -5.0), (60.0, 10.0, -5.0))) == 0.0


def test_jpeg_quality():
    rng = np.random.default_rng(1)
    im = _img(rng.integers(0, 256, (64, 64, 3)).astype(np.uint8))
    for q in (50, 75, 95):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        est = benchmark.jpeg_quality(Image.open(io.BytesIO(buf.getvalue())))
        assert abs(est - q) <= 1, (q, est)


def test_gaussian_filter():
    x = np.full((8, 8), 3.0)
    assert np.allclose(benchmark.gaussian_filter(x), 3.0)
    # impulse response integrates to 1
    x = np.zeros((16, 16))
    x[8, 8] = 1.0
    assert abs(benchmark.gaussian_filter(x).sum() - 1.0) < 1e-9


def test_best_shift():
    # vertical stripes, period 16 > 2*reach so the shift is unambiguous
    W, H = 64, 32
    o = (np.arange(W)[None, :] % 16 < 2).repeat(H, axis=0) * 255
    o = np.stack([o] * 3, axis=2).astype(np.uint8)
    r = np.roll(o, shift=3, axis=1)  # content moved +3 px in x
    blur = lambda im: np.asarray(im.filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 255.0
    dx, dy, _ = diffcheck.best_shift(blur(Image.fromarray(o)), blur(Image.fromarray(r)), 0, 0, W, H, reach=6)
    assert (dx, dy) == (-3.0, 0.0), (dx, dy)


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")


if __name__ == "__main__":
    main()
