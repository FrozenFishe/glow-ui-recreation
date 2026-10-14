"""Run the recreation pipeline for any design, driven by one project file.

Every design-specific value lives in projects/<name>/project.json: the design image and size, the element and
text specs, the photos and strips shipped as original pixels, the drawn shapes in drawing order (which ones sit
on a photo, which discs to subtract), the exact-mode sections, parts and clips. The tools themselves are generic.

  tools/recreate.py new <name> <design.png|jpg>        scaffold projects/<name>/ (project.json, empty specs)
  tools/recreate.py <name> slice                        trace elements and text            (slicer.py)
  tools/recreate.py <name> tune                         tune traces, make cutouts          (tune.py)
  tools/recreate.py <name> parts                        split untraceable parts            (split_parts.py)
  tools/recreate.py <name> clips                        clip elements to their regions     (clip_elements.py)
  tools/recreate.py <name> plate                        background + full-res plate        (backdrop.py --plate)
  tools/recreate.py <name> shapes [--under img] [--edge-band N] [--only a,b] [--stroke-widths ..]   fit drawn shapes (tune_shapes.py)
  tools/recreate.py <name> kit <tool> [--photo-edges N] [--out dir]   editor/web kit for one renderer (make_kit.py)
  tools/recreate.py <name> exact [--out dir]            exact mode: original as layers     (exact_layers.py)
  tools/recreate.py <name> calibrate <tool> <render_max.png>          one calibration round (calibrate.py)
  tools/recreate.py <name> inkgain <tool> W=render.png [W=render.png ...]                      (inkgain.py)
  tools/recreate.py <name> diff <render.png>            region report + heatmap            (diffcheck.py)
  tools/recreate.py <name> bench Label=render.png [...] score against the original           (benchmark.py)
  tools/recreate.py <name> all                          slice, tune, parts, clips, plate, shapes, exact

<tool> is a renderer name (website, photoshop, photocraft, affinity, ...): it selects that renderer's
calibration_<tool>.json and ink_gain_<tool>.json. Paths in project.json are relative to the repo root.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PY = sys.executable
T = lambda name: os.path.join(ROOT, "tools", name)
R = lambda p: os.path.join(ROOT, p)


def run(*args):
    print("+", " ".join(str(a) for a in args))
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)


def load(name):
    return json.load(open(R(f"projects/{name}/project.json")))


def per_tool(p, key, tool):
    return R(p[key].format(tool=tool))


def new(name, design):
    from PIL import Image
    d = R(f"projects/{name}")
    os.makedirs(os.path.join(d, "specs"), exist_ok=True)
    ext = os.path.splitext(design)[1].lower()
    dst = os.path.join(d, "design" + ext)
    if os.path.abspath(design) != dst:
        import shutil
        shutil.copyfile(design, dst)
    W, H = Image.open(dst).size
    rel = lambda *a: os.path.relpath(os.path.join(d, *a), ROOT)
    proj = {
        "name": name, "title": name, "design": rel("design" + ext), "size": [W, H],
        "specs": {"components": rel("specs", "components.json"), "text": rel("specs", "text.json"), "regions": rel("specs", "regions.json")},
        "raw": {"components": rel("build", "components"), "text": rel("build", "text")},
        "manifests": {"components": rel("build", "components_tuned", "manifest.json"), "text": rel("build", "text_tuned", "manifest.json")},
        "shapes": rel("specs", "shapes.json"), "shapes_tuned": rel("build", "shapes_tuned.json"),
        "parts": rel("specs", "parts.json"), "clips": rel("specs", "clips.json"),
        "plate": rel("build", "backdrop_plate.webp"), "backdrop": rel("build", "backdrop.png"),
        "calibration": rel("build", "calibration_{tool}.json"), "ink_gain": rel("build", "ink_gain_{tool}.json"),
        "build": rel("build"),
        "photos": [], "strips": [], "photo_under": None, "repeat": [], "drawn": [], "rims": [],
        "sections": [{"name": "Page", "rest": True}],
    }
    for k, v in {"components": [], "text": [], "regions": {}, "shapes": [], "parts": [], "clips": []}.items():
        f = os.path.join(d, "specs", f"{k}.json")
        if not os.path.exists(f):
            json.dump(v, open(f, "w"), indent=1)
    json.dump(proj, open(os.path.join(d, "project.json"), "w"), indent=1)
    print(f"created projects/{name}/ ({W}x{H}). Next: fill specs/*.json and project.json (photos, drawn, sections),\n"
          f"then: tools/recreate.py {name} all   (see the README: 'Recreate any design')")


def step(name, cmd, args):
    p = load(name)
    design = R(p["design"])
    man = [R(p["manifests"]["components"]), R(p["manifests"]["text"])]
    photo_boxes = [ph["box"] for ph in p.get("photos", []) if ph["name"] != p.get("photo_under")]
    opt = lambda flag, default=None: args[args.index(flag) + 1] if flag in args else default
    if cmd == "slice":
        for k in ("components", "text"):
            if json.load(open(R(p["specs"][k]))):
                run(PY, T("slicer.py"), design, R(p["specs"][k]), R(p["raw"][k]))
    elif cmd == "tune":
        for k in ("components", "text"):
            raw = os.path.join(R(p["raw"][k]), "manifest.json")
            if os.path.exists(raw):
                run(PY, T("tune.py"), design, raw, os.path.dirname(R(p["manifests"][k])))
    elif cmd == "parts":
        if os.path.exists(R(p["parts"])) and json.load(open(R(p["parts"]))):
            run(PY, T("split_parts.py"), design, man[0], R(p["parts"]))
    elif cmd == "clips":
        if os.path.exists(R(p["clips"])) and json.load(open(R(p["clips"]))):
            for m in man:
                run(PY, T("clip_elements.py"), m, R(p["clips"]))
    elif cmd == "plate":
        masks = [f"{x},{y},{w},{h}" for ph in p.get("photos", []) for x, y, w, h in [ph["box"]]]
        a = [PY, T("backdrop.py"), design, R(p["backdrop"]), "--plate", R(p["plate"])]
        for m in man:
            if os.path.exists(m):
                a += ["--manifest", m]
        for m in masks:
            a += ["--mask", m]
        run(*a)
    elif cmd == "shapes":
        if not json.load(open(R(p["shapes"]))):
            print("no shapes in", p["shapes"]); return
        a = [PY, T("tune_shapes.py"), design, R(p["shapes"]), R(p["shapes_tuned"])]
        for m in man:
            if os.path.exists(m):
                a += ["--exclude", m]
        for x, y, w, h in photo_boxes:
            a += ["--exclude-box", f"{x},{y},{w},{h}"]
        for flag in ("--under", "--edge-band", "--only", "--stroke-widths", "--max-move"):
            if opt(flag):
                a += [flag, opt(flag)]
        run(*a)
    elif cmd == "kit":
        tool = args[0]
        out = opt("--out", R(os.path.join(p["build"], f"kit_{tool}")))
        a = [PY, T("make_kit.py"), out, "--project", R(f"projects/{name}/project.json")]
        if os.path.exists(per_tool(p, "calibration", tool)):
            a += ["--calibration", per_tool(p, "calibration", tool)]
        if os.path.exists(per_tool(p, "ink_gain", tool)) and tool not in ("photoshop",):
            a += ["--ink", per_tool(p, "ink_gain", tool)]
        if opt("--photo-edges"):
            a += ["--photo-edges", opt("--photo-edges")]
        run(*a)
    elif cmd == "exact":
        run(PY, T("exact_layers.py"), design, R(p["plate"]), opt("--out", R(os.path.join(p["build"], "exact"))),
            "--project", R(f"projects/{name}/project.json"))
    elif cmd == "calibrate":
        tool, render = args[0], args[1]
        cal = per_tool(p, "calibration", tool)
        a = [PY, T("calibrate.py"), design, render, R(p["shapes_tuned"]), cal]
        for m in man:
            a += ["--exclude", m]
        for x, y, w, h in photo_boxes:
            a += ["--exclude-box", f"{x},{y},{w},{h}"]
        if os.path.exists(cal):
            a += ["--prev", cal]
        run(*a)
    elif cmd == "inkgain":
        tool = args[0]
        a = [PY, T("inkgain.py"), design, per_tool(p, "ink_gain", tool)]
        for r in args[1:]:
            a += ["--render", r]
        run(*a)
    elif cmd == "diff":
        a = [PY, T("diffcheck.py"), design, args[0]]
        if os.path.exists(R(p["specs"]["regions"])) and json.load(open(R(p["specs"]["regions"]))):
            a += ["--regions", R(p["specs"]["regions"])]
        run(*a, "--out", os.path.splitext(args[0])[0] + "_diff.png")
    elif cmd == "bench":
        a = [PY, T("benchmark.py"), design]
        for e in args:
            a += ["--entry", e]
        run(*a)
    elif cmd == "all":
        for c in ("slice", "tune", "parts", "clips", "plate", "shapes", "exact"):
            step(name, c, [])
    else:
        sys.exit(__doc__)


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if a[0] == "new":
        new(a[1], a[2])
    else:
        step(a[0], a[1] if len(a) > 1 else "", a[2:])


if __name__ == "__main__":
    main()
