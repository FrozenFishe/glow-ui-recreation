"""Find the font that matches a line of text in a design image, one to one.

Renders the same text in every candidate font (the whole Google Fonts catalog
for a category, plus every font installed on this Mac), scales it to the same
height as the text in the image, and scores how well the letter shapes
overlap (IoU of the ink masks). The best candidates are then refined over
letter-spacing. Prints a ranking and writes a JSON report and a preview sheet.

usage: fontmatch.py <image> --box x y w h --text "Searching and booking"
                    [--category serif] [--italic] [--top 10] [--out report.json]

Scoring is per letter: the line is split into glyphs, each candidate letter is
scaled by the same factor (line heights matched) and its shape compared with the
original letter (IoU), so spacing differences don't drown out shape differences.
Score guide (mean letter IoU): >= 0.80 is a near-exact match, 0.70-0.80 a close
lookalike, < 0.70 means the font is probably commercial or custom: build one from the
image with glyphfont.py instead.
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from fontTools.ttLib import TTCollection, TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from slicer import background, inkness  # noqa: E402

RENDER_PX = 160
CACHE = os.path.join(os.path.dirname(__file__), ".fontcache")
SYSTEM_DIRS = ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
UA = "Mozilla/5.0 fontmatch"  # a non-browser UA makes the CSS API return TrueType


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


UP = 3  # compare at 3x so thin serifs survive thresholding


def target_mask(image_path, box):
    x, y, w, h = box
    rgb = np.asarray(Image.open(image_path).convert("RGB")).astype(float)[y:y + h, x:x + w]
    ink = inkness(rgb, background(rgb))
    big = Image.fromarray((ink * 255).astype(np.uint8)).resize((w * UP, h * UP), Image.LANCZOS)
    return crop_to_ink(np.array(big) > 127)


def crop_to_ink(mask):
    ys, xs = np.where(mask)
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def components(mask):
    """Connected components (8-neighbour) as (x0, y0, x1, y1) boxes."""
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    boxes = []
    for sy, sx in zip(*np.nonzero(mask)):
        if seen[sy, sx]:
            continue
        stack, seen[sy, sx] = [(sy, sx)], True
        x0 = x1 = sx
        y0 = y1 = sy
        while stack:
            cy, cx = stack.pop()
            x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if (x1 - x0 + 1) * (y1 - y0 + 1) >= 4:
            boxes.append([x0, y0, x1 + 1, y1 + 1])
    return boxes


def glyph_boxes(mask, text):
    """Split a line mask into one box per visible character of text (left to right)."""
    boxes = sorted(components(mask), key=lambda b: b[0])
    merged = []
    for b in boxes:
        if merged:
            m = merged[-1]
            overlap = min(m[2], b[2]) - max(m[0], b[0])
            if overlap > 0.4 * min(m[2] - m[0], b[2] - b[0]):
                merged[-1] = [min(m[0], b[0]), min(m[1], b[1]), max(m[2], b[2]), max(m[3], b[3])]
                continue
        merged.append(b)
    chars = [c for c in text if not c.isspace()]
    # repair: slanted/touching letters merge, stray specks split off
    while len(merged) < len(chars):
        i = max(range(len(merged)), key=lambda j: merged[j][2] - merged[j][0])
        x0, y0, x1, y1 = merged[i]
        cols = mask[y0:y1, x0:x1].sum(axis=0)
        lo, hi = (x1 - x0) // 4, 3 * (x1 - x0) // 4
        cut = x0 + lo + int(np.argmin(cols[lo:hi])) if hi > lo else (x0 + x1) // 2
        merged[i:i + 1] = [[x0, y0, cut, y1], [cut, y0, x1, y1]]
    while len(merged) > len(chars):
        i = min(range(len(merged)), key=lambda j: (merged[j][2] - merged[j][0]) * (merged[j][3] - merged[j][1]))
        n = i - 1 if i and (i == len(merged) - 1 or merged[i][0] - merged[i - 1][2] < merged[i + 1][0] - merged[i][2]) else i + 1
        a, b = merged[min(i, n)], merged[max(i, n)]
        merged[min(i, n):max(i, n) + 1] = [[min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]]
    for b in merged:  # shrink each box to its ink
        ys, xs = np.nonzero(mask[b[1]:b[3], b[0]:b[2]])
        b[:] = [b[0] + xs.min(), b[1] + ys.min(), b[0] + xs.max() + 1, b[1] + ys.max() + 1]
    return list(zip(chars, merged))


def render(font_bytes, text, tracking_em=0.0, index=0):
    font = ImageFont.truetype(io.BytesIO(font_bytes), RENDER_PX, index=index)
    width = int(sum(font.getlength(c) for c in text) + RENDER_PX * (abs(tracking_em) * len(text) + 2))
    img = Image.new("L", (width, RENDER_PX * 3), 0)
    draw, x = ImageDraw.Draw(img), RENDER_PX
    for c in text:
        draw.text((x, RENDER_PX), c, font=font, fill=255)
        x += font.getlength(c) + tracking_em * RENDER_PX
    return crop_to_ink(np.array(img) > 127)


def iou_centered(a, b):
    h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
    def place(m):
        c = np.zeros((h, w), bool)
        oy, ox = (h - m.shape[0]) // 2, (w - m.shape[1]) // 2
        c[oy:oy + m.shape[0], ox:ox + m.shape[1]] = m
        return c
    A, B = place(a), place(b)
    return (A & B).sum() / max((A | B).sum(), 1)


def score(font_bytes, index, text, target, glyphs):
    """Mean per-letter IoU at a common scale (line heights matched), plus the scale itself."""
    line = render(font_bytes, text, 0.0, index)
    scale = target.shape[0] / line.shape[0]
    font = ImageFont.truetype(io.BytesIO(font_bytes), RENDER_PX, index=index)
    total = []
    for ch, (x0, y0, x1, y1) in glyphs:
        img = Image.new("L", (RENDER_PX * 3, RENDER_PX * 3), 0)
        ImageDraw.Draw(img).text((RENDER_PX, RENDER_PX // 2), ch, font=font, fill=255)
        m = np.array(img) > 127
        if not m.any():
            return 0.0, scale
        g = crop_to_ink(m)
        g = np.array(Image.fromarray(g.astype(np.uint8) * 255).resize(
            (max(1, round(g.shape[1] * scale)), max(1, round(g.shape[0] * scale))), Image.BILINEAR)) > 127
        total.append(iou_centered(g, target[y0:y1, x0:x1]))
    return float(np.mean(total)), scale


def covers(tt, text):
    cmap = tt.getBestCmap() or {}
    return all(ord(c) in cmap for c in set(text) if not c.isspace())


def google_candidates(category, italic, text):
    meta = json.loads(fetch("https://fonts.google.com/metadata/fonts").decode().lstrip(")]}'\n"))
    out = []
    for fam in meta["familyMetadataList"]:
        if category != "all" and fam["category"].lower().replace(" ", "-") != category:
            continue
        styles = [k for k in fam["fonts"] if k.endswith("i") == italic]
        for st in styles:
            wght = int(st.rstrip("i"))
            if not 300 <= wght <= 600:
                continue
            out.append((fam["family"], wght))
    return out


def google_font(family, wght, italic, text):
    os.makedirs(CACHE, exist_ok=True)
    key = re.sub(r"\W", "_", f"{family}_{wght}_{int(italic)}_{text}")[:150]
    path = os.path.join(CACHE, key + ".ttf")
    if not os.path.exists(path):
        q = urllib.parse.quote(family) + f":ital,wght@{int(italic)},{wght}"
        css = fetch(f"https://fonts.googleapis.com/css2?family={q}&text={urllib.parse.quote(text)}").decode()
        url = re.search(r"url\((https://[^)]+)\)", css).group(1)
        open(path, "wb").write(fetch(url))
    return open(path, "rb").read()


def system_candidates(italic, text):
    out = []
    for d in SYSTEM_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            path = os.path.join(d, fn)
            if not fn.lower().endswith((".ttf", ".otf", ".ttc")):
                continue
            try:
                fonts = TTCollection(path).fonts if fn.lower().endswith(".ttc") else [TTFont(path, lazy=True)]
            except Exception:
                continue
            for i, tt in enumerate(fonts):
                try:
                    name = tt["name"]
                    fam = name.getBestFamilyName()
                    sub = name.getBestSubFamilyName() or ""
                except Exception:
                    continue
                if ("italic" in sub.lower() or "oblique" in sub.lower()) != italic or not covers(tt, text):
                    continue
                out.append((f"{fam} {sub}".strip(), path, i))
    return out


def evaluate(args):
    label, source, data, index, text, target, glyphs = args
    try:
        s, scale = score(data, index, text, target, glyphs)
        return {"font": label, "source": source, "score": s, "index": index, "data": data, "scale": scale}
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--box", nargs=4, type=int, required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--category", default="serif", help="serif, sans-serif, display, handwriting, monospace or all")
    ap.add_argument("--italic", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default="fontmatch.json")
    a = ap.parse_args()

    target = target_mask(a.image, a.box)
    text = a.text
    glyphs = glyph_boxes(target, text)
    jobs = []

    gc = google_candidates(a.category, a.italic, text)
    print(f"Google Fonts candidates: {len(gc)}", file=sys.stderr)
    with ThreadPoolExecutor(16) as pool:
        datas = list(pool.map(lambda fw: (fw, _safe(google_font, fw[0], fw[1], a.italic, text)), gc))
    for (fam, w), data in datas:
        if data:
            jobs.append((f"{fam} {w}{' italic' if a.italic else ''}", "google", data, 0, text, target, glyphs))
    for label, path, i in system_candidates(a.italic, text):
        jobs.append((label, "system:" + path, open(path, "rb").read(), i, text, target, glyphs))
    print(f"Scoring {len(jobs)} fonts…", file=sys.stderr)

    with ThreadPoolExecutor(8) as pool:
        results = [r for r in pool.map(evaluate, jobs) if r]
    results.sort(key=lambda r: -r["score"])

    # letter-spacing that reproduces the line width at the matched size
    for r in results[:a.top]:
        line = render(r["data"], text, 0.0, r["index"])
        gap = (target.shape[1] - line.shape[1] * r["scale"]) / max(len(text) - 1, 1)
        r["tracking_em"] = round(gap / (RENDER_PX * r["scale"]), 3)
    leaders = results[:a.top]

    # font-size in image px that reproduces the text height: RENDER_PX * scale
    report = [{"rank": i + 1, "font": r["font"], "source": r["source"].replace(os.path.expanduser("~"), "~"), "score": round(r["score"], 4),
               "font_size_px": round(RENDER_PX * r["scale"] / UP, 2), "tracking_em": r.get("tracking_em", 0.0)}
              for i, r in enumerate(leaders)]
    verdict = ("near-exact match" if report[0]["score"] >= 0.80 else
               "close lookalike" if report[0]["score"] >= 0.70 else
               "no good match: build a custom font with glyphfont.py")
    json.dump({"text": text, "box": a.box, "verdict": verdict, "ranking": report}, open(a.out, "w"), indent=1)

    sheet(target, leaders, text, os.path.splitext(a.out)[0] + ".png")
    for r in report:
        print(f'{r["rank"]:2}. {r["score"]:.3f}  {r["font"]:45} size {r["font_size_px"]}px  tracking {r["tracking_em"]:+.2f}em  [{r["source"].split(":")[0]}]')
    print("verdict:", verdict)


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def sheet(target, leaders, text, path):
    """Target in black with each candidate overlaid in red: grey = overlap, red/black = mismatch."""
    th, tw = target.shape
    rows = []
    for r in leaders[:6]:
        cand = render(r["data"], text, r.get("tracking_em", 0.0), r["index"])
        img = Image.fromarray(cand.astype(np.uint8) * 255).resize((max(1, round(cand.shape[1] * th / cand.shape[0])), th))
        c = np.zeros((th, max(tw, img.width)), bool)
        c[:, :img.width] = np.array(img) > 127
        t = np.zeros_like(c)
        t[:, :tw] = target
        rgb = np.full(c.shape + (3,), 255, np.uint8)
        rgb[t & ~c] = (0, 0, 0)
        rgb[c & ~t] = (230, 40, 40)
        rgb[c & t] = (150, 150, 150)
        rows.append(Image.fromarray(rgb))
    W = max(r.width for r in rows) + 20
    out = Image.new("RGB", (W, sum(r.height + 30 for r in rows)), "white")
    d, y = ImageDraw.Draw(out), 0
    for r, row in zip(leaders, rows):
        d.text((10, y + 4), f'{r["font"]}  IoU {r["score"]:.3f}', fill=(0, 0, 0))
        out.paste(row, (10, y + 24))
        y += row.height + 30
    out.save(path)


if __name__ == "__main__":
    main()
