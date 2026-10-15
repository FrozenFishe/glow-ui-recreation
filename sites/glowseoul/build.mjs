// GlowSeoul site build: src/ + the recreation project (projects/glowseoul) -> dist/
//   traced vectors + cutouts (tools/slicer.py, tools/tune.py), tuned shapes (tools/tune_shapes.py, fit_pills.py),
//   fonts traced from the design (tools/glyphfont.py), the Photoshop clean plate, exact layers (tools/exact_layers.py).
import { readFileSync, writeFileSync, mkdirSync, cpSync, existsSync, rmSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const P = "../../projects/glowseoul/build";
const OUT = process.env.OUT || "dist";
const J = (f) => JSON.parse(readFileSync(f, "utf8"));
const hash = (f) => createHash("sha1").update(readFileSync(f)).digest("hex").slice(0, 8);
const n3 = (v) => Math.round(v * 1000) / 1000;

const COMP = J(`${P}/components_tuned/manifest.json`);
const TEXT = J(`${P}/text_tuned/manifest.json`);
const SHAPES = J(`${P}/shapes_tuned.json`);
const PILLS = J(`${P}/pills.json`);
const EXACT = J(`${P}/exact/layers.json`);
const FIT = existsSync("code_fit.json") ? J("code_fit.json") : {};
const INK = existsSync(`${P}/ink_gain_website.json`) ? J(`${P}/ink_gain_website.json`) : {};

rmSync(OUT, { recursive: true, force: true });
mkdirSync(`${OUT}/px`, { recursive: true });
mkdirSync(`${OUT}/exact`, { recursive: true });
mkdirSync(`${OUT}/fonts`, { recursive: true });
cpSync("src/assets", `${OUT}/assets`, { recursive: true });
cpSync("src/design", `${OUT}/design`, { recursive: true });

// lossless WebP for everything shipped as original pixels
const py = "../../tools/.venv/bin/python";
const webp = (src, dst) => execFileSync(py, ["-c", `from PIL import Image; Image.open(${JSON.stringify(src)}).save(${JSON.stringify(dst)}, lossless=True, method=6)`]);
webp(`${P}/plate.png`, `${OUT}/assets/plate.webp`);
for (const c of [...COMP, ...TEXT]) if (c.raster) webp(`${P}/${COMP.includes(c) ? "components_tuned" : "text_tuned"}/${c.raster}`, `${OUT}/px/${c.name}.webp`);
for (const l of EXACT) webp(`${P}/exact/${l.file}`, `${OUT}/exact/${l.file.replace(".png", ".webp")}`);
for (const [d, f] of [["display", "GlowSeoulDisplay-Light"], ["italic", "GlowSeoulItalic-Italic"], ["serif", "GlowSeoulSerif-Regular"]])
  cpSync(`${P}/fonts/${d}/${f}.woff2`, `${OUT}/fonts/${f}.woff2`);

// pixel layer: each traced element as an inline SVG at its design box; elements tune.py kept as rasters (tiny ones)
// show their original-pixel cutout instead. Max mode shows the cutout for every element.
const pos = (b) => `--x:${b[0]};--y:${b[1]};--w:${b[2]};--h:${b[3]}`;
const item = (c) => {
  const auto = c.mode === "raster";
  const ink = process.env.INK_ALL ? Number(process.env.INK_ALL) : INK[c.name] || 0;
  const stroke = ink ? ` stroke="${c.colour}" stroke-width="${ink}" stroke-linejoin="round"` : "";
  const svg = `<svg class="px-v${auto ? " has-r" : ""}" data-n="${c.name}" style="${pos(c.box)}" viewBox="0 0 ${c.box[2]} ${c.box[3]}"><path fill="${c.colour}"${stroke} d="${c.d}"/></svg>`;
  return svg + `<img class="px-r${auto ? " r-auto" : ""}" data-n="${c.name}" src="px/${c.name}.webp?v=${hash(`${OUT}/px/${c.name}.webp`)}" width="${c.raster_box[2]}" height="${c.raster_box[3]}" alt="" style="${pos(c.raster_box)}">`;
};
const icons = COMP.map(item).join("");
const textPx = TEXT.map(item).join("");

// shapes: tuned geometry (fractional design px) as CSS on the live elements
const shapeCss = SHAPES.map((s) => {
  const sel = s.name === "cta" ? ".cta" : `.cat[data-n="${s.name}"]`;
  return `${sel}{--ox:${n3(s.box[0])}px;--oy:${n3(s.box[1])}px;left:${n3(s.box[0])}px;top:${n3(s.box[1])}px;width:${n3(s.box[2])}px;height:${n3(s.box[3])}px;border-radius:${n3(s.r)}px;background:${s.fill}}`;
}).join("\n");
const pill = (sel, p) => {
  const [r, g, b, a] = p.rgba;
  return `${sel}{--ox:${p.box[0]}px;--oy:${p.box[1]}px;left:${p.box[0]}px;top:${p.box[1]}px;width:${p.box[2]}px;height:${p.box[3]}px;border-radius:${p.r}px;background:rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},${Math.min(a, 1).toFixed(3)})}`;
};

// code mode: live text in the traced fonts (headline, logo) and Inter, fitted to each element's ink box (fit_code.py)
const FONTS = {
  logo: "400 33.8px 'GlowSeoul Serif'", tx_head_1: "300 64.35px 'GlowSeoul Display'", tx_head_2: "300 64.35px 'GlowSeoul Display'",
  tx_head_3: "300 64.35px 'GlowSeoul Display'", tx_ship: "600 11.6px Inter", tx_cta: "500 15.6px Inter", tx_search: "400 14.2px Inter",
};
const fontOf = (n) => FONTS[n] || (n.startsWith("tx_nav") ? "400 15.6px Inter" : n.startsWith("tx_p") ? "400 16.9px Inter"
  : n.startsWith("tx_f") ? "400 11.4px Inter" : "400 13.2px Inter");
const codeCss = [...TEXT, COMP.find((c) => c.name === "logo")].map((c) => {
  const f = FIT[c.name] || { dx: 0, dy: 0, k: 1, ls: 0 };
  const [w, size, ...fam] = fontOf(c.name).split(" ");
  const px = parseFloat(size) * f.k;
  return `.stage .t[data-n="${c.name}"]{left:calc(${n3(c.box[0] + f.dx)}px - var(--ox, 0px));top:calc(${n3(c.box[1] + f.dy)}px - var(--oy, 0px));font:${w} ${n3(px)}px/1 ${fam.join(" ")}, Inter, sans-serif;letter-spacing:${n3(f.ls)}px;color:${c.colour}}`;
}).join("\n");

// exact mode: the original as layers (background + 8 sections), stacked as backgrounds
const exactBg = EXACT.slice().reverse().map((l) => `url(exact/${l.file.replace(".png", ".webp")}?v=${hash(`${OUT}/exact/${l.file.replace(".png", ".webp")}`)}) 0 0/1672px 941px no-repeat`).join(",\n    ");

const css = readFileSync("src/styles.css", "utf8")
  .replace("/*generated*/", `/* generated by build.mjs */
.stage{background:url(assets/plate.webp?v=${hash(`${OUT}/assets/plate.webp`)}) 0 0/1672px 941px no-repeat}
${pill(".search", PILLS.search)}
${pill(".ship", PILLS.ship)}
${shapeCss}
${codeCss}
@media (min-width: 900px) {
  .exact .stage{background:${exactBg}}
}`);
writeFileSync(`${OUT}/styles.css`, css);
const html = readFileSync("src/index.html", "utf8")
  .replace("<!--icons-->", `<div class="px px-icons" aria-hidden="true">${icons}</div>`)
  .replace("<!--pixel-->", `<div class="px px-text" aria-hidden="true">${textPx}</div>`)
  .replace("__PLATE__", `assets/plate.webp?v=${hash(`${OUT}/assets/plate.webp`)}`)
  .replace("__CSSV__", hash(`${OUT}/styles.css`));
writeFileSync(`${OUT}/index.html`, html);
console.log(`built ${OUT}: ${COMP.length} icons, ${TEXT.length} text elements, ${SHAPES.length + 2} shapes, ${EXACT.length} exact layers`);
