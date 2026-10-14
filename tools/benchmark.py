"""Benchmark recreations against the original design, with a measured noise floor.

Metrics (all computed at the original's size):
  changed %  share of pixels that differ by > 12% after a 0.7px blur (the diffcheck.py measure)
  SSIM       structural similarity (Gaussian window, sigma 1.5), 1 = identical
  dE2000     CIEDE2000 colour difference per pixel: mean and 95th percentile
             (dE < 1 is invisible, 1-2 is barely visible to a trained eye)
  PSNR       peak signal-to-noise ratio in dB (higher is closer)

The noise floor shows how much the original differs from *itself* after one
JPEG re-save at its own quality: differences below that floor are compression
noise, not recreation error.

usage: benchmark.py <original> --entry "Label=path.png" [--entry ...] [--json out.json] [--md out.md]
"""
import argparse
import io
import json

import numpy as np
from PIL import Image, ImageFilter


def load_rgb(path_or_img, size):
    im = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(path_or_img)
    im = im.convert("RGB")
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return im


def changed_pct(a, b):
    blur = lambda im: np.asarray(im.filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 255.0
    return float((np.abs(blur(a) - blur(b)).mean(axis=2) > 0.12).mean() * 100)


def gaussian_filter(x, sigma=1.5):
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.pad(x, r, mode="reflect")
    # separable convolution
    h = np.zeros((pad.shape[0], x.shape[1]))
    for i in range(2 * r + 1):
        h += k[i] * pad[:, i:i + x.shape[1]]
    v = np.zeros_like(x, dtype=np.float64)
    for i in range(2 * r + 1):
        v += k[i] * h[i:i + x.shape[0], :]
    return v


def ssim(a, b):
    """Mean SSIM on luminance (Wang et al. 2004)."""
    y = lambda im: np.asarray(im.convert("L"), dtype=np.float64)
    x1, x2 = y(a), y(b)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu1, mu2 = gaussian_filter(x1), gaussian_filter(x2)
    s11 = gaussian_filter(x1 * x1) - mu1 ** 2
    s22 = gaussian_filter(x2 * x2) - mu2 ** 2
    s12 = gaussian_filter(x1 * x2) - mu1 * mu2
    m = ((2 * mu1 * mu2 + C1) * (2 * s12 + C2)) / ((mu1 ** 2 + mu2 ** 2 + C1) * (s11 + s22 + C2))
    return float(m.mean())


def to_lab(im):
    rgb = np.asarray(im, dtype=np.float64) / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return L, a, b


def ciede2000(lab1, lab2):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    hs = h1p + h2p
    hbp = np.where(C1p * C2p == 0, hs, np.where(np.abs(h1p - h2p) <= 180, hs / 2, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2)))
    T = 1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp)) + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63))
    dth = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dth)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def psnr(a, b):
    mse = np.mean((np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)) ** 2)
    return float("inf") if mse == 0 else float(10 * np.log10(255 ** 2 / mse))


def jpeg_quality(im):
    """Estimate the JPEG quality from the luminance quantisation table (IJG scaling)."""
    q = getattr(im, "quantization", None)
    if not q:
        return None
    base = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
            18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
    t = list(q[0])
    scale = np.mean([t[i] / base[i] for i in range(64)]) * 100
    return int(round((200 - scale) / 2)) if scale <= 100 else int(round(5000 / scale))


def measure(orig, img):
    return {"changed_pct": round(changed_pct(orig, img), 3), "ssim": round(ssim(orig, img), 4),
            "dE_mean": round(float(np.mean(de := ciede2000(to_lab(orig), to_lab(img)))), 3),
            "dE_p95": round(float(np.percentile(de, 95)), 3), "psnr": round(psnr(orig, img), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("--entry", action="append", default=[], help="Label=path")
    ap.add_argument("--json")
    ap.add_argument("--md")
    a = ap.parse_args()

    src = Image.open(a.original)
    quality = jpeg_quality(src)
    orig = src.convert("RGB")
    size = orig.size
    rows = []

    # noise floor: the original re-saved once at its own quality, and at quality 95
    for label, q in ((f"Floor: original re-saved as JPEG q{quality}", quality or 90), ("Floor: original re-saved as JPEG q95", 95)):
        buf = io.BytesIO()
        orig.save(buf, "JPEG", quality=q)
        rows.append({"label": label, **measure(orig, Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))})

    for e in a.entry:
        label, path = e.split("=", 1)
        rows.append({"label": label, **measure(orig, load_rgb(path, size))})

    head = "| Version | Changed % | SSIM | ΔE2000 mean | ΔE2000 p95 | PSNR dB |\n|---|---|---|---|---|---|\n"
    md = head + "".join(f"| {r['label']} | {r['changed_pct']:.3f} | {r['ssim']:.4f} | {r['dE_mean']:.3f} | {r['dE_p95']:.3f} | {r['psnr']:.2f} |\n" for r in rows)
    print(f"original: {a.original}  estimated JPEG quality {quality}\n")
    print(md)
    if a.json:
        json.dump({"jpeg_quality": quality, "rows": rows}, open(a.json, "w"), indent=1)
    if a.md:
        open(a.md, "w").write(md)


if __name__ == "__main__":
    main()
