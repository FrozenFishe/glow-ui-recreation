// Fluttering Penguins site build: src/ + the recreation project (projects/penguins) -> dist/
//   traced vectors + cutouts (tools/slicer.py, tune.py, split_parts.py), tuned shapes (tools/tune_shapes.py), the
//   fitted outline button (projects/penguins/tools/fit_pill.py), the Photoshop/plate background, exact layers.
import { readFileSync, writeFileSync, mkdirSync, cpSync, existsSync, rmSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const PR = "../../projects/penguins", P = `${PR}/build`;
const OUT = process.env.OUT || "dist";
const J = (f) => JSON.parse(readFileSync(f, "utf8"));
const hash = (f) => createHash("sha1").update(readFileSync(f)).digest("hex").slice(0, 8);
const n3 = (v) => Math.round(v * 1000) / 1000;
const py = "../../tools/.venv/bin/python";

const COMP = J(`${P}/components_tuned/manifest.json`);
const TEXT = J(`${P}/text_tuned/manifest.json`);
const SHAPES = J(`${P}/shapes_tuned.json`);
const DRAWN = J(`${PR}/project.json`).drawn;
const PILL = J(`${P}/pill.json`);
const EXACT = J(`${process.env.EXACT || `${process.env.HOME}/Downloads/penguins_kit/exact`}/layers.json`);
const EXDIR = process.env.EXACT || `${process.env.HOME}/Downloads/penguins_kit/exact`;
const FIT = existsSync("code_fit.json") ? J("code_fit.json") : {};
const INK = existsSync(`${P}/ink_gain_website.json`) ? J(`${P}/ink_gain_website.json`) : {};
// live text: the same list the Photoshop build uses (name, string, font, size, x, baseline, colour)
const LIVE = Object.fromEntries([...readFileSync(`${PR}/editors/photoshop/live_text.jsx`, "utf8").matchAll(/mk\("(\w+)","(.*?)","Pretendard-(\w+)",([\d.]+),([\d.]+),([\d.]+),"(\w+)"\)/g)]
  .map((m) => [m[1], { s: m[2], w: { Regular: 400, Medium: 500, SemiBold: 600, Bold: 700 }[m[3]], size: +m[4], x: +m[5], base: +m[6], col: "#" + m[7] }]));

rmSync(OUT, { recursive: true, force: true });
for (const d of ["px", "exact", "fonts", "assets"]) mkdirSync(`${OUT}/${d}`, { recursive: true });

const webp = (src, dst, extra = "") => execFileSync(py, ["-c", `from PIL import Image; im=Image.open(${JSON.stringify(src)})${extra}; im.save(${JSON.stringify(dst)}, lossless=True, method=6)`]);
const lossy = (src, dst, w) => execFileSync(py, ["-c", `from PIL import Image; im=Image.open(${JSON.stringify(src)}).convert('RGB'); im=im.resize((${w}, round(im.height*${w}/im.width)), Image.LANCZOS) if im.width>${w} else im; im.save(${JSON.stringify(dst)}, quality=82, method=6)`]);
webp(`${P}/plate.png`, `${OUT}/assets/plate.webp`);
const pillBox = JSON.parse(execFileSync(py, ["-c", `from PIL import Image; im=Image.open('${P}/pill.png'); b=im.getbbox(); im.crop(b).save('${OUT}/px/btn2_fill.webp', lossless=True, method=6); print(list(b))`]).toString());
for (const c of [...COMP, ...TEXT]) if (c.raster) webp(`${P}/${COMP.includes(c) ? "components_tuned" : "text_tuned"}/${c.raster}`, `${OUT}/px/${c.name}.webp`);
for (const l of EXACT) webp(`${EXDIR}/${l.file}`, `${OUT}/exact/${l.file.replace(".png", ".webp")}`);
// small-screen photos (the Photoshop slices: UI removed by content-aware fill)
lossy(`${PR}/slices/photoshop/hero.png`, `${OUT}/assets/hero-m.webp`, 1214);
lossy(`${PR}/slices/photoshop/story_photo.png`, `${OUT}/assets/story_photo.webp`, 934);
execFileSync(py, ["-c", `from PIL import Image; im=Image.open('${P}/components_tuned/logo_icon_tones-raster.png').convert('RGBA'); s=max(im.size); c=Image.new('RGBA',(s,s)); c.paste(im,((s-im.width)//2,(s-im.height)//2)); c.resize((64,64),Image.LANCZOS).save('${OUT}/assets/favicon.png')`]);
// Pretendard (OFL), subset to the characters on the page
const html0 = readFileSync("src/index.html", "utf8");
const chars = [...new Set((html0.replace(/<[^>]+>/g, "") + Object.values(LIVE).map((t) => t.s).join("") + "0123456789+%,.→♡♥").split(""))].join("");
const FONTSRC = process.env.PRETENDARD || "fonts-src";
for (const w of ["Regular", "Medium", "SemiBold", "Bold"])
  execFileSync("../../tools/.venv/bin/pyftsubset", [`${FONTSRC}/Pretendard-${w}.woff2`, `--text=${chars}`, "--flavor=woff2", `--output-file=${OUT}/fonts/Pretendard-${w}.woff2`, "--layout-features=*"]);

// pixel layer: each traced element as an inline SVG at its design box; elements tune.py kept as rasters show their
// original-pixel cutout. Max mode shows the cutout for every element (parts excepted: their parent's cutout has them).
const pos = (b) => `--x:${b[0]};--y:${b[1]};--w:${b[2]};--h:${b[3]}`;
const item = (c) => {
  const auto = c.mode === "raster";
  const ink = process.env.INK_ALL ? Number(process.env.INK_ALL) : INK[c.name] || 0;
  const stroke = ink ? ` stroke="${c.colour}" stroke-width="${ink}" stroke-linejoin="round"` : "";
  const svg = c.d ? `<svg class="px-v${auto ? " has-r" : ""}" data-n="${c.name}" style="${pos(c.box)}" viewBox="0 0 ${c.box[2]} ${c.box[3]}"><path fill="${c.colour}"${stroke} d="${c.d}"/></svg>` : "";
  return svg + `<img class="px-r${auto ? " r-auto" : ""}${c.part_of ? " part" : ""}" data-n="${c.name}" src="px/${c.name}.webp?v=${hash(`${OUT}/px/${c.name}.webp`)}" width="${c.raster_box[2]}" height="${c.raster_box[3]}" alt="" style="${pos(c.raster_box)}">`;
};
const pillImg = `<img class="px-r fill" style="--x:${pillBox[0]};--y:${pillBox[1]};--w:${pillBox[2] - pillBox[0]};--h:${pillBox[3] - pillBox[1]}" src="px/btn2_fill.webp?v=${hash(`${OUT}/px/btn2_fill.webp`)}" alt="">`;
// the fitted button is drawn below the vectors; shown in every desktop mode except exact
const pxLayer = `<div class="px px-shapes" aria-hidden="true">${pillImg.replace("px-r fill", "fillb")}</div><div class="px px-icons" aria-hidden="true">${COMP.map(item).join("")}</div><div class="px px-text" aria-hidden="true">${TEXT.map(item).join("")}</div>`;

// shapes: tuned geometry as CSS; children of a shape are placed in page coordinates minus its --ox/--oy
const shapeCss = SHAPES.map((s) => {
  const d = DRAWN.find((x) => x.name === s.name) || {};
  const sw = s.stroke ? s.sw || d.sw || 1 : 0;
  const r = s.kind === "circle" ? "50%" : `${n3(s.r)}px`;
  return `.shape[data-n="${s.name}"]{--ox:${n3(s.box[0])}px;--oy:${n3(s.box[1])}px;left:${n3(s.box[0])}px;top:${n3(s.box[1])}px;width:${n3(s.box[2])}px;height:${n3(s.box[3])}px;border-radius:${r};background:${s.fill};${sw ? `border:${sw}px solid ${s.stroke};` : ""}}`;
}).join("\n");
const ruleCss = DRAWN.filter((d) => d.kind === "line").map((d) => `.rule[data-n="${d.name}"]{left:${d.points[0] - 0.5}px;top:${d.points[1]}px;width:1px;height:${d.points[3] - d.points[1]}px;background:${d.stroke}}`).join("\n");
const ghost = `.ghost{left:${n3(PILL.box[0])}px;top:${n3(PILL.box[1])}px;width:${n3(PILL.box[2])}px;height:${n3(PILL.box[3])}px;border-radius:${n3(PILL.r)}px;--ox:${n3(PILL.box[0])}px;--oy:${n3(PILL.box[1])}px}
.px .fillb{display:block}.exact .px-shapes{visibility:hidden}`;
const lang = TEXT.find((t) => t.name === "tx_lang").box;
const langCss = `.lang{left:${lang[0] - 4}px;top:${lang[1] - 8}px;width:${lang[2] + 26}px;height:${lang[3] + 16}px;--ox:${lang[0] - 4}px;--oy:${lang[1] - 8}px}`;

// live text positions (code mode): Pretendard's baseline sits 0.855 em below the top of a line-height:1 box
const codeCss = TEXT.map((c) => {
  const t = LIVE[c.name]; if (!t) return "";
  const f = FIT[c.name] || { dx: 0, dy: 0, k: 1, ls: 0 };
  const size = t.size * f.k;
  return `.t[data-n="${c.name}"]{left:calc(${n3(t.x + f.dx)}px - var(--ox, 0px));top:calc(${n3(t.base - 0.855 * size + f.dy)}px - var(--oy, 0px));font:${t.w} ${n3(size)}px/1 Pretendard, sans-serif;letter-spacing:${n3(f.ls)}px;color:${c.colour}}`;
}).join("\n");

const exactBg = EXACT.slice().reverse().map((l) => `url(exact/${l.file.replace(".png", ".webp")}?v=${hash(`${OUT}/exact/${l.file.replace(".png", ".webp")}`)}) 0 0/1214px 1295px no-repeat`).join(",\n    ");
const css = readFileSync("src/styles.css", "utf8").replace("/*generated*/", `/* generated by build.mjs */
@media (min-width: 900px) {
.stage{background:url(assets/plate.webp?v=${hash(`${OUT}/assets/plate.webp`)}) 0 0/1214px 1295px no-repeat}
${shapeCss}
${ruleCss}
${ghost}
${langCss}
${codeCss}
.exact .stage{background:${exactBg}}
}
@media (max-width: 899px) {
${SHAPES.filter((s) => s.kind === "circle").map((s) => `.circ[data-n="${s.name}"]{background:${s.fill}}`).join("\n")}
}`);
writeFileSync(`${OUT}/styles.css`, css);
writeFileSync(`${OUT}/index.html`, html0
  .replace("<!--pixel-->", pxLayer)
  .replace("__PLATE__", `assets/plate.webp?v=${hash(`${OUT}/assets/plate.webp`)}`)
  .replace("__CSSV__", hash(`${OUT}/styles.css`)));
writeFileSync(`${OUT}/404.html`, `<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>페이지를 찾을 수 없습니다 | Fluttering Penguins</title><style>body{font-family:system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;background:#f6f9fe;color:#14305f}a{color:#255397}</style><main><h1>404</h1><p>페이지를 찾을 수 없습니다. <a href="/">홈으로</a></p></main>`);
console.log(`built ${OUT}: ${COMP.length} icons, ${TEXT.length} text elements, ${SHAPES.length} shapes, ${EXACT.length} exact layers`);
