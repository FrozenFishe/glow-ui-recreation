"""Build a font from the letters in a design image, for when no existing font matches.

Every line of text you give it (box + the exact text) is split into glyphs,
each glyph is traced with potrace into vector outlines, and the outlines are
assembled into an OpenType (CFF) font with the spacing measured from the
image. The result reproduces the design's lettering exactly for the
characters that appear in it; list a fallback font (fontmatch.py's best
lookalike) after it in your font stack for any other characters.

usage: glyphfont.py <image> <spec.json> <out-dir>

spec: {"family": "Glow Display", "style": "Regular", "italic": false,
       "lines": [{"box": [x, y, w, h], "text": "Searching and booking"}, ...]}

Writes <Family>-<Style>.otf, .woff2 and a JSON report with the font size in
image pixels that reproduces the design (use it as the CSS / editor size).
"""
import json
import os
import sys

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from fontmatch import UP, components, glyph_boxes  # noqa: E402
from slicer import background, inkness, trace, UPSCALE  # noqa: E402

UPM = 1000
DESCENDERS = set("gjpqy,;")
FLAT_TOPS = set("acemnorsuvwxz")
ASCENDERS = set("bdfhklt") | set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

GLYPH_NAMES = {" ": "space", ".": "period", ",": "comma", "'": "quotesingle", "&": "ampersand",
               "+": "plus", "-": "hyphen", "/": "slash", ":": "colon", "!": "exclam", "?": "question"}


def glyph_name(ch):
    return GLYPH_NAMES.get(ch, ch if ch.isalnum() and ch.isascii() else f"uni{ord(ch):04X}")


def label(mask):
    """8-connected component labels (0 = background) and the number of components."""
    h, w = mask.shape
    labels = np.zeros((h, w), np.int32)
    n = 0
    for sy, sx in zip(*np.nonzero(mask)):
        if labels[sy, sx]:
            continue
        n += 1
        stack = [(sy, sx)]
        labels[sy, sx] = n
        while stack:
            cy, cx = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = n
                        stack.append((ny, nx))
    return labels, n


def line_glyphs(image, box, text):
    x, y, w, h = box
    rgb = image[y:y + h, x:x + w]
    ink = inkness(rgb, background(rgb))
    big = np.array(Image.fromarray((ink * 255).astype(np.uint8)).resize((w * UP, h * UP), Image.LANCZOS)) / 255.0
    mask = big > 0.5
    ys, xs = np.where(mask)
    oy, ox = ys.min(), xs.min()
    crop_mask = mask[oy:, ox:]
    glyphs = glyph_boxes(crop_mask[: ys.max() - oy + 1, : xs.max() - ox + 1], text)
    labels, count = label(mask)
    # every connected ink blob belongs to exactly one glyph: the one whose box holds most of it,
    # so slivers of a neighbouring letter that poke into a glyph's box are never copied into it
    owner = {}
    for lab in range(1, count + 1):
        ys_l, xs_l = np.nonzero(labels == lab)
        cx = xs_l.mean() - ox
        best = min(range(len(glyphs)), key=lambda i: 0 if glyphs[i][1][0] <= cx < glyphs[i][1][2]
                   else min(abs(cx - glyphs[i][1][0]), abs(cx - glyphs[i][1][2])))
        owner.setdefault(best, []).append(lab)
    out = []
    for i, (ch, (x0, y0, x1, y1)) in enumerate(glyphs):
        keep = np.isin(labels, owner.get(i, []))
        ys_k, xs_k = np.nonzero(keep)
        gx0, gy0, gx1, gy1 = xs_k.min(), ys_k.min(), xs_k.max() + 1, ys_k.max() + 1
        pad = 2 * UP
        sy0, sx0 = max(gy0 - pad, 0), max(gx0 - pad, 0)
        # include anti-aliased edge pixels around the kept blobs (dilate by 2px), nothing else
        grow = np.array(Image.fromarray(keep.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
        sub = (big * grow)[sy0:gy1 + pad, sx0:gx1 + pad]
        out.append({"ch": ch, "box": (gx0, gy0, gx1, gy1), "ink": sub, "origin": (sx0, sy0)})
    return out


def measure(lines):
    """Baseline per line, and the font's em size in UP-scaled pixels."""
    for ln in lines:
        bottoms = [g["box"][3] for g in ln["glyphs"] if g["ch"] not in DESCENDERS]
        ln["baseline"] = float(np.median(bottoms))
    xh = [ln["baseline"] - g["box"][1] for ln in lines for g in ln["glyphs"] if g["ch"] in FLAT_TOPS]
    asc = [ln["baseline"] - g["box"][1] for ln in lines for g in ln["glyphs"] if g["ch"] in ASCENDERS]
    # Typical book faces: ascender ~0.72 em; fall back to x-height ~0.46 em.
    em = (np.median(asc) / 0.72) if asc else (np.median(xh) / 0.46)
    return em, (float(np.median(xh)) if xh else None)


def build(spec, image_path, out_dir):
    image = np.asarray(Image.open(image_path).convert("RGB")).astype(float)
    lines = []
    for ln in spec["lines"]:
        lines.append({"text": ln["text"], "glyphs": line_glyphs(image, ln["box"], ln["text"])})
    em_px, xheight = measure(lines)
    k = UPM / em_px  # font units per UP-scaled pixel

    # side bearings from the measured gaps between neighbouring letters
    glyphs, spaces = {}, []
    for ln in lines:
        gs, text = ln["glyphs"], ln["text"]
        visible = [i for i, c in enumerate(text) if not c.isspace()]
        for n, g in enumerate(gs):
            prev_gap = gs[n]["box"][0] - gs[n - 1]["box"][2] if n else None
            next_gap = gs[n + 1]["box"][0] - g["box"][2] if n + 1 < len(gs) else None
            ti = visible[n]
            space_before = n and any(text[j].isspace() for j in range(visible[n - 1] + 1, ti))
            space_after = n + 1 < len(gs) and any(text[j].isspace() for j in range(ti + 1, visible[n + 1]))
            if space_after:
                spaces.append(next_gap)
            lsb = None if (prev_gap is None or space_before) else prev_gap / 2
            rsb = None if (next_gap is None or space_after) else next_gap / 2
            rec = glyphs.setdefault(g["ch"], {"g": g, "baseline": ln["baseline"], "lsb": [], "rsb": []})
            if lsb is not None:
                rec["lsb"].append(lsb)
            if rsb is not None:
                rec["rsb"].append(rsb)
    all_sb = [v for r in glyphs.values() for v in r["lsb"] + r["rsb"]] or [em_px * 0.04]
    default_sb = float(np.median(all_sb))
    space_gap = float(np.median(spaces)) if spaces else em_px * 0.25

    fb = FontBuilder(UPM, isTTF=False)
    order = [".notdef", "space"] + [glyph_name(c) for c in sorted(glyphs)]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({32: "space", **{ord(c): glyph_name(c) for c in glyphs}})

    charstrings, metrics = {}, {}
    pen = T2CharStringPen(500, None)
    pen.moveTo((50, 0)); pen.lineTo((450, 0)); pen.lineTo((450, 700)); pen.lineTo((50, 700)); pen.closePath()
    charstrings[".notdef"], metrics[".notdef"] = pen.getCharString(), (500, 50)
    space_adv = round(max(space_gap - 2 * default_sb, em_px * 0.12) * k)
    charstrings["space"], metrics["space"] = T2CharStringPen(space_adv, None).getCharString(), (space_adv, 0)

    ymin_all, ymax_all = 0, 0
    for ch, rec in glyphs.items():
        g = rec["g"]
        lsb = float(np.median(rec["lsb"])) if rec["lsb"] else default_sb
        rsb = float(np.median(rec["rsb"])) if rec["rsb"] else default_sb
        gx0, _, gx1, _ = g["box"]
        ox, oy = g["origin"]
        base = rec["baseline"]
        adv = round((lsb + (gx1 - gx0) + rsb) * k)
        pen = T2CharStringPen(adv, None)
        for sp in trace(g["ink"]):
            for seg in sp:
                pts = [(round(((ox + seg[i] / UPSCALE) - gx0 + lsb) * k), round((base - (oy + seg[i + 1] / UPSCALE)) * k))
                       for i in range(1, len(seg), 2)]
                if seg[0] == "M":
                    pen.moveTo(pts[0])
                elif seg[0] == "L":
                    pen.lineTo(pts[0])
                elif seg[0] == "C":
                    pen.curveTo(*pts)
                else:
                    pen.closePath()
                for _, py in pts:
                    ymin_all, ymax_all = min(ymin_all, py), max(ymax_all, py)
        charstrings[glyph_name(ch)] = pen.getCharString()
        metrics[glyph_name(ch)] = (adv, round(lsb * k))

    family, style = spec["family"], spec.get("style", "Regular")
    ps = f"{family.replace(' ', '')}-{style.replace(' ', '')}"
    fb.setupCFF(ps, {"FullName": f"{family} {style}"}, charstrings, {})
    fb.setupHorizontalMetrics(metrics)
    asc, desc = max(ymax_all, 800), min(ymin_all, -200)
    fb.setupHorizontalHeader(ascent=asc, descent=desc)
    fb.setupNameTable({"familyName": family, "styleName": style, "psName": ps,
                       "uniqueFontIdentifier": f"{ps}-glyphfont"})
    italic = spec.get("italic", False)
    fb.setupOS2(sTypoAscender=asc, sTypoDescender=desc, usWinAscent=asc, usWinDescent=-desc,
                sxHeight=round(xheight * k) if xheight else 450, fsSelection=0x01 if italic else 0x40,
                usWeightClass=400)
    fb.setupPost(italicAngle=-12 if italic else 0)
    fb.updateHead(macStyle=0x02 if italic else 0x00)

    os.makedirs(out_dir, exist_ok=True)
    otf = os.path.join(out_dir, ps + ".otf")
    fb.save(otf)
    fb.font.flavor = "woff2"
    fb.save(os.path.join(out_dir, ps + ".woff2"))
    report = {"family": family, "style": style, "otf": os.path.basename(otf), "woff2": ps + ".woff2",
              "font_size_px": round(em_px / UP, 2), "characters": "".join(sorted(glyphs)),
              "note": "Set the font size to font_size_px (image pixels) to reproduce the design; "
                      "add a fallback font for characters not listed."}
    json.dump(report, open(os.path.join(out_dir, ps + ".json"), "w"), indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    build(json.load(open(sys.argv[2])), sys.argv[1], sys.argv[3])
