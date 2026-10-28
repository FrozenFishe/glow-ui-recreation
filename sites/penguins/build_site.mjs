// Fluttering Penguins: build the live site (src/site) into dist/, then the 1:1 replica (build.mjs) into dist/replica/.
//   icons: multi-tone vectors traced from the design (projects/penguins/tools/trace_tones.py), inlined
//   photos: Photoshop slices (UI removed), Real-ESRGAN 2x (tools/enhance.py), WebP at 1x and 2x
//   fonts: Pretendard (OFL), subset to the characters the page uses (Korean + English)
import { readFileSync, writeFileSync, mkdirSync, rmSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const PR = "../../projects/penguins", OUT = "dist", py = "../../tools/.venv/bin/python";
const hash = (s) => createHash("sha1").update(s).digest("hex").slice(0, 8);
rmSync(OUT, { recursive: true, force: true });
for (const d of ["img", "fonts"]) mkdirSync(`${OUT}/${d}`, { recursive: true });

// photos: [source, out name, widths]
const PHOTOS = [["hero", "hero", [1214, 2428]], ["impact_banner", "impact", [1160, 2320]], ["story_photo", "story", [467, 934]]];
for (const [src, name, widths] of PHOTOS)
  execFileSync(py, ["-c", `from PIL import Image
im = Image.open('${PR}/build/hd/${src}-2x.jpg').convert('RGB')
if '${name}' == 'impact':  # the slice carries the banner's own rounded border: trim it (2 design px), CSS draws the edge
    im = im.crop((4, 4, im.width - 4, im.height - 4))
    # the left half is a plain gradient under the copy: blur away content-aware-fill leftovers, fading into the photo
    import numpy as np
    from PIL import ImageFilter
    a = np.asarray(im).astype(float); b = np.asarray(im.filter(ImageFilter.GaussianBlur(24))).astype(float)
    x = np.arange(im.width) / im.width; w = np.clip((0.62 - x) / 0.1, 0, 1)[None, :, None]
    im = Image.fromarray(np.round(a * (1 - w) + b * w).astype('uint8'))
for w in ${JSON.stringify(widths)}:
    im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save('${OUT}/img/${name}-%d.webp' % w, quality=86, method=6)`]);

// icons
const icon = (n) => readFileSync(`${PR}/build/tones/${n}.svg`, "utf8")
  .replace(/ width="[\d.]+" height="[\d.]+"/, ` aria-hidden="true" focusable="false" class="i-${n}"`);
writeFileSync(`${OUT}/img/logo.svg`, readFileSync(`${PR}/build/tones/logo.svg`, "utf8"));

const css = readFileSync("src/site/site.css", "utf8"), js = readFileSync("src/site/app.js", "utf8");
writeFileSync(`${OUT}/site.css`, css); writeFileSync(`${OUT}/app.js`, js);
let html = readFileSync("src/site/index.html", "utf8").replace(/__ICON_(\w+)__/g, (_, n) => icon(n))
  .replace("__CSSV__", hash(css)).replace("__JSV__", hash(js));
writeFileSync(`${OUT}/index.html`, html);

// fonts: every character in the page and the script, plus printable ASCII
let chars = new Set((html + js).replace(/<svg[\s\S]*?<\/svg>/g, ""));
for (let c = 32; c < 127; c++) chars.add(String.fromCharCode(c));
chars = [...chars].filter((c) => c.charCodeAt(0) >= 32).join("");
writeFileSync("build-chars.txt", chars);
for (const w of ["Regular", "Medium", "SemiBold", "Bold"])
  execFileSync("../../tools/.venv/bin/pyftsubset", [`fonts-src/Pretendard-${w}.woff2`, "--text-file=build-chars.txt", "--flavor=woff2",
    `--output-file=${OUT}/fonts/Pretendard-${w}.woff2`, "--layout-features=*"]);
writeFileSync(`${OUT}/404.html`, `<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>페이지를 찾을 수 없습니다 | Fluttering Penguins</title><link rel="icon" href="/img/logo.svg"><style>body{font-family:system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;background:#f3f7fd;color:#152f5e;text-align:center}a{color:#255397}</style><main><h1>404</h1><p>페이지를 찾을 수 없습니다. <a href="/">홈으로</a></p></main>`);

// the 1:1 replica (pixel / max / exact / code modes)
execFileSync("node", ["build.mjs"], { env: { ...process.env, OUT: `${OUT}/replica` }, stdio: "inherit" });
console.log("site:", readdirSync(`${OUT}/img`).join(" "));
