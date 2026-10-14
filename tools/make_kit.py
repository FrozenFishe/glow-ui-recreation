"""Build the editor import kit: everything an editor needs to rebuild the design, as files that
any of them can place (Photoshop, PhotoCraft, Affinity, Illustrator...).

  backdrop.png                      the original's background shading (from framework/backdrop.png)
  hero_exact.png, thumb_*_exact.png lossless photo slices
  shapes_tuned.svg                  every drawn shape, geometry/colours from tools/glow_shapes_tuned.json
  vectors_tuned.svg                 tuned vectors for elements drawn as vectors
  vectors_tiny_hidden.svg           tuned vectors for tiny elements (hide; for 2x / editing)
  vectors_all.svg                   both of the above
  cutouts_tiny.png                  original-pixel cutouts of the tiny elements (standard mode)
  cutouts_all_max_fidelity.png      original-pixel cutouts of every traced element (max-fidelity mode)

All files are 1536x1024 design coordinates. Layer order, bottom to top: backdrop, hero, shapes,
card photos, vectors, tiny cutouts (+ hidden max-fidelity cutouts).

usage: make_kit.py <out-dir>
"""
import copy
import json
import os
import sys

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SVG_HEAD = '<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024">'


def shapes_svg(tuned):
    T = {s["name"]: s for s in tuned if not (s.get("tune") or {}).get("kept")}

    def rect(n, x, y, w, h, r, fill, stroke=None, sw=1):
        if n in T:
            x, y, w, h = T[n]["box"]; r = T[n].get("r", r); fill = T[n]["fill"]; stroke = T[n].get("stroke", stroke)
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        ins = sw / 2 if stroke else 0  # SVG strokes are centred: inset so the outer edge matches the box
        return f'<rect id="{n}" x="{x + ins}" y="{y + ins}" width="{w - 2 * ins}" height="{h - 2 * ins}" rx="{max(r - ins, 0)}" fill="{fill}"{s}/>'

    def circ(n, x, y, d, fill, stroke, sw=1):
        if n in T:
            x, y, d, _ = T[n]["box"]; fill = T[n]["fill"]; stroke = T[n].get("stroke", stroke)
        return f'<circle id="{n}" cx="{x + d / 2}" cy="{y + d / 2}" r="{d / 2 - sw / 2}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'

    def line(n, x1, y1, x2, y2, c):
        return f'<line id="{n}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="1"/>'

    S = [line("strip_divider", 0, 893.5, 1536, 893.5, "#ECECEC"),
         rect("location_pill", 1132, 39, 192, 48, 24, "#F7F7F7", "#E6E6E6"), rect("signup", 1338, 38, 161, 50, 25, "#000001"),
         rect("search_bar", 58, 545, 636, 72, 26, "#FEFEFE", "#E9E9E9"), line("search_divider", 347.5, 557, 347.5, 605, "#E6E6E6"),
         rect("search_button", 569, 557, 113, 48, 18, "#111214")]
    for n, x in [("ring_search", 87), ("ring_book", 248), ("ring_enjoy", 408), ("ring_trusted", 566)]:
        S.append(circ(n, x, 667, 66, "#FBFBFB", "#E8E8E8"))
    for i, x in enumerate([201, 361, 520]):
        S.append(line(f"feature_divider_{i + 1}", x + .5, 700, x + .5, 757, "#DDDDDD"))
    S.append('<path id="screen" fill="#F7F7F7" d="M1125,188 H1340 A42,42 0 0 1 1382,230 V817 A44,44 0 0 1 1338,861 H1127 A44,44 0 0 1 1083,817 V230 A42,42 0 0 1 1125,188 Z"/>')
    S.append('<path id="tab_bar_strip" fill="#FEFEFE" d="M1083,791 H1382 V817 A44,44 0 0 1 1338,861 H1127 A44,44 0 0 1 1083,817 Z"/>')
    S.append(line("tab_divider", 1083, 790.5, 1382, 790.5, "#F0F0F0"))
    S.append(rect("island", 1192, 196, 82, 24, 12, "#000000"))
    S.append(rect("app_search", 1098, 308, 230, 37, 10, "#FEFEFE", "#ECECEC"))
    S.append(rect("app_filter", 1331, 308, 36, 37, 10, "#FEFEFE", "#ECECEC"))
    for i in range(5):
        S.append(rect(f"tile_{i + 1}", 1098 + i * 55.3, 401, 48, 77, 10, "#EFEDEB"))
    for i, y in enumerate([535, 656]):
        S.append(rect(f"card_{i + 1}", 1097, y, 270, 111, 10, "#FCFCFB", "#EFEFEF"))
    for i, y in enumerate([612, 733]):
        S.append(rect(f"book_{i + 1}", 1307, y, 52, 23, 11.5, "#060606"))
    S.append(rect("home_indicator", 1181, 851, 103, 4, 2, "#111111"))
    S.append(circ("badge", 1360, 732, 140, "#FEFEFE", "#E4E4E4"))
    return SVG_HEAD + "".join(S) + "</svg>"


def main(out):
    os.makedirs(out, exist_ok=True)
    p = lambda *a: os.path.join(ROOT, *a)
    o = Image.open(p("variants/shared/original.jpg")).convert("RGB")
    o.crop((712, 0, 1536, 894)).save(os.path.join(out, "hero_exact.png"))
    o.crop((1104, 543, 1184, 640)).save(os.path.join(out, "thumb_facial_exact.png"))
    o.crop((1104, 664, 1184, 760)).save(os.path.join(out, "thumb_lash_exact.png"))
    Image.open(p("framework/backdrop.png")).convert("RGB").resize((1536, 1024), Image.BILINEAR).save(os.path.join(out, "backdrop.png"))
    open(os.path.join(out, "shapes_tuned.svg"), "w").write(shapes_svg(json.load(open(p("tools/glow_shapes_tuned.json")))))

    comp = json.load(open(p("variants/shared/components_tuned/manifest.json")))
    text = json.load(open(p("variants/shared/text_all_tuned/manifest.json")))
    items = []
    for c in comp:
        items.append((c, p("variants/shared/components_tuned")))
        if c["name"] in ("card_star", "card_bookmark"):  # card 2 reuses card 1's icons, 121px lower
            d = copy.deepcopy(c); d["name"] += "_2"; d["box"][1] += 121; d["raster_box"][1] += 121
            items.append((d, p("variants/shared/components_tuned")))
    items += [(c, p("variants/shared/text_all_tuned")) for c in text]
    vis, hid = [], []
    tiny = Image.new("RGBA", (1536, 1024), (0, 0, 0, 0))
    allc = Image.new("RGBA", (1536, 1024), (0, 0, 0, 0))
    for c, d in items:
        path = f'<path id="{c["name"]}" fill="{c["colour"]}" transform="translate({c["box"][0]},{c["box"][1]})" d="{c["d"]}"/>'
        (hid if c["mode"] == "raster" else vis).append(path)
        cut = Image.open(os.path.join(d, c["raster"])).convert("RGBA")
        allc.alpha_composite(cut, tuple(c["raster_box"][:2]))
        if c["mode"] == "raster":
            tiny.alpha_composite(cut, tuple(c["raster_box"][:2]))
    open(os.path.join(out, "vectors_tuned.svg"), "w").write(SVG_HEAD + "".join(vis) + "</svg>")
    open(os.path.join(out, "vectors_tiny_hidden.svg"), "w").write(SVG_HEAD + "".join(hid) + "</svg>")
    open(os.path.join(out, "vectors_all.svg"), "w").write(SVG_HEAD + "".join(vis + hid) + "</svg>")
    tiny.save(os.path.join(out, "cutouts_tiny.png"))
    allc.save(os.path.join(out, "cutouts_all_max_fidelity.png"))
    print(f"kit written to {out}: {len(vis)} vectors, {len(hid)} tiny elements")


if __name__ == "__main__":
    main(sys.argv[1])
