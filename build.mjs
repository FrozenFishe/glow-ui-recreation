// Builds dist/<variant> for each editor: shared site source + that editor's image cuts,
// the Glow UI framework (tokens, CSS, traced icons, fonts), a /design notes page and a /framework page.
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";

const MANIFEST = JSON.parse(readFileSync("variants/shared/components/manifest.json", "utf8"));
const TOKENS = JSON.parse(readFileSync("framework/tokens.json", "utf8"));
const icons = MANIFEST.filter((c) => !c.name.startsWith("logo_") || c.name === "logo_glow" || c.name === "logo_sparkle");
const brands = MANIFEST.filter((c) => c.name.startsWith("logo_") && !["logo_glow", "logo_sparkle"].includes(c.name));
const BRAND_NAMES = { logo_mecca: "MECCA", logo_adorebeauty: "Adore Beauty", logo_benefit: "Benefit Cosmetics", logo_endota: "Endota Spa",
  logo_sephora: "Sephora", logo_elleebana: "Elleebana", logo_kevinmurphy: "Kevin.Murphy" };

// one <symbol> per traced icon; fill follows CSS color
const SPRITE = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none">${icons.map((c) =>
  `<symbol id="gl-${c.name}" viewBox="0 0 ${c.box[2]} ${c.box[3]}"><path d="${c.d}"/></symbol>`).join("")}</svg>`;
const LOGOS = `<ul class="logos" role="list">${brands.map((c) =>
  `<li style="--x:${c.box[0]};--y:${c.box[1] - 893};--w:${c.box[2]}"><img src="framework/logos/${c.svg}" width="${c.box[2]}" height="${c.box[3]}" alt="${BRAND_NAMES[c.name] || c.name}"></li>`).join("")}</ul>`;

const SITES = {
  affinity: process.env.AFFINITY_URL || "",
  photocraft: process.env.PHOTOCRAFT_URL || "",
};

const VARIANTS = {
  affinity: {
    name: "Affinity",
    method: "Affinity JavaScript SDK (MCP) scripts building vector, text and image layers",
    source: "glow_landing.af",
  },
  photocraft: {
    name: "PhotoCraft",
    method: "PhotoCraft MCP commands (batched) building shape, text and pixel layers",
    source: "glow.pcraft",
  },
};

const STATS = [
  ["Ran", "First, with no prior knowledge", "Second, given coordinates, colours and fonts from the Affinity run"],
  ["Tokens used (context)", "≈174k (≈135k excluding ≈40k session overhead)", "≈146k"],
  ["Tool calls", "≈82", "58"],
  ["Calls that built the page", "3 full build scripts (≈15 KB each)", "13 command batches + 4 single commands"],
  ["Main token cost", "Reading SDK docs and finding the right APIs", "Shape commands returning their full path data"],
  ["Slicing", "Cut with sips (outside Affinity), then placed as image layers", "Slice tool marked the regions; Save for Web is blocked over the API, so cut by crop, save and undo"],
  ["Editable layers", "164 layers in 8 groups", "133 layers"],
  ["v2 upgrade: approach", "One 13 KB script reading the shared manifest (traced icons, logos, fonts, 2x photos)", "Wrote all traced paths to one SVG, opened it, pasted the group in place"],
  ["v2 upgrade: tool calls", "≈10 (2 build runs + checks)", "81"],
  ["v2 upgrade: tokens", "≈25k (script + 2 runs; the shared tools did the heavy lifting)", "≈151k (two 133-layer doc_inspect dumps ≈50k)"],
  ["Measured-fix pass", "2 script runs after an Affinity restart (fonts), ≈15k tokens", "≈22 tool calls, ≈65k tokens (type.setStyle echoes)"],
  ["v2 headline", "Live text in the custom Glow Display font", "Traced outlines (the server started before the font was installed)"],
  ["Measured mismatch (tools/diffcheck.py)", "3.80% of pixels → 2.28% after measured corrections", "2.22% (traced headline) → 1.76% after measured corrections"],
];

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");

function slider(a, la, b, lb) {
  return `<div class="compare" style="--pos:50%">
  <img src="${a}" alt="${la}" width="1536" height="1024">
  <div class="top"><img src="${b}" alt="${lb}" width="1536" height="1024"></div>
  <input type="range" min="0" max="100" value="50" aria-label="Compare ${la} and ${lb}" oninput="this.parentNode.style.setProperty('--pos', this.value + '%')">
  <span class="tag l">${la}</span><span class="tag r">${lb}</span>
</div>`;
}

function designPage(key) {
  const v = VARIANTS[key];
  const otherKey = key === "affinity" ? "photocraft" : "affinity";
  const other = SITES[otherKey] ? `<a href="${SITES[otherKey]}/design">See the ${VARIANTS[otherKey].name} version →</a>` : "";
  const rows = STATS.map(([k, a, p]) => `<tr><th scope="row">${esc(k)}</th><td${key === "affinity" ? ' class="me"' : ""}>${esc(a)}</td><td${key === "photocraft" ? ' class="me"' : ""}>${esc(p)}</td></tr>`).join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glow — ${v.name} recreation</title>
<link rel="stylesheet" href="design.css"></head>
<body><main>
<p class="crumb"><a href="/">← Live site</a> ${other}</p>
<h1>Glow, recreated in ${v.name}</h1>
<p class="lede">A one-to-one rebuild of the Glow landing-page design using ${esc(v.method)}. The photographic parts (hero photo, card thumbnails, brand logos) are slices cut from the original. Everything else is editable text and shapes. The live site at <a href="/">/</a> is responsive HTML and CSS built from these slices.</p>

<h2>Original vs. ${v.name} v2</h2>
<p class="hint">Drag the handle to compare. v2 uses traced icons and logos, the custom Glow Display font and AI-upscaled photos.</p>
${slider("design/original.jpg", "Original", "design/render-v2.jpg", v.name + " v2")}
<h2>${v.name} v1 → v2</h2>
<p class="hint">v1 had hand-drawn icons, a single logo strip and lookalike fonts.</p>
${slider("design/render.jpg", v.name + " v1", "design/render-v2.jpg", v.name + " v2")}
<p class="crumb" style="margin-top:28px"><a href="/framework">Glow UI framework →</a> <a href="https://github.com/FrozenFishe/glow-ui-recreation">Source on GitHub →</a></p>

<h2>Affinity vs. PhotoCraft</h2>
<div class="tablewrap"><table>
<thead><tr><th></th><th scope="col"${key === "affinity" ? ' class="me"' : ""}>Affinity</th><th scope="col"${key === "photocraft" ? ' class="me"' : ""}>PhotoCraft</th></tr></thead>
<tbody>${rows}</tbody></table></div>
<p class="note">Token figures come from the context counter, not a billing meter, so treat them as approximate. The comparison isn't like-for-like: the PhotoCraft run was given the layout measurements the Affinity run had to work out, which saved it a lot of exploration.</p>
</main></body></html>`;
}

const DESIGN_CSS = `:root{--ink:#111;--muted:#5a5a5a;--line:#e6e6e6;--bg:#f6f6f6;--card:#fff;--accent:#111}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--ink);font:16px/1.6 "Helvetica Neue",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:1100px;margin:0 auto;padding:32px 16px 64px}a{color:inherit}
.crumb{display:flex;justify-content:space-between;gap:16px;font-size:14px}
h1{font:400 clamp(32px,6vw,52px)/1.1 "Bodoni 72",Didot,Georgia,serif;margin:28px 0 12px}
h2{font-size:18px;font-weight:600;margin:40px 0 8px}.lede{color:var(--muted);max-width:720px}.hint,.note{color:var(--muted);font-size:14px}
.compare{position:relative;margin-top:12px;border-radius:12px;overflow:hidden;background:#ddd;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.compare img{display:block;width:100%;height:auto}
.compare .top{position:absolute;inset:0;clip-path:inset(0 0 0 var(--pos))}
.compare .top::before{content:"";position:absolute;top:0;bottom:0;left:var(--pos);border-left:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.35)}
.compare input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:ew-resize;margin:0}
.tag{position:absolute;top:10px;font-size:12px;background:rgba(17,17,17,.75);color:#fff;padding:3px 8px;border-radius:99px;pointer-events:none}.tag.l{left:10px}.tag.r{right:10px}
.tablewrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;min-width:560px;font-size:14px}th,td{text-align:left;vertical-align:top;padding:12px 14px;border-bottom:1px solid var(--line)}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}thead th{font-size:13px}tbody th{font-weight:500;color:var(--muted);width:24%}
.me{background:#fafaf7;font-weight:500}.note{margin-top:12px;max-width:760px}`;

const NOT_FOUND = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Not found — Glow</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f6f6f6;color:#111;font:16px "Helvetica Neue",Arial,sans-serif;text-align:center}h1{font:400 44px Georgia,serif;margin:0 0 8px}a{color:inherit}</style></head>
<body><div><h1>Page not found</h1><p><a href="/">Back to Glow</a></p></div></body></html>`;

function frameworkPage() {
  const swatches = Object.entries(TOKENS.color).map(([k, v]) =>
    `<li><span class="sw" style="background:${v.$value}"></span><b>${k}</b><code>${v.$value}</code><small>${esc(v.$description || "")}</small></li>`).join("");
  const fam = (f) => (f === "display" ? "var(--gl-font-display)" : "var(--gl-font-sans)");
  const types = Object.entries(TOKENS.type).map(([k, v]) => {
    const t = v.$value;
    const style = `font-family:${fam(t.family)};font-size:${Math.min(t.size, 56)}px;font-weight:${t.weight || 400};${t.tracking ? `letter-spacing:${t.tracking}em;` : ""}${t.case === "upper" ? "text-transform:uppercase;" : ""}`;
    return `<li><code>${k}</code><span style="${style}">Searching and booking</span><small>${t.size}px${t.lineHeight ? ` / ${t.lineHeight}` : ""}${t.weight ? ` · ${t.weight}` : ""} — ${esc(v.$description || "")}</small></li>`;
  }).join("");
  const iconList = icons.map((c) =>
    `<li><svg class="gl-icon" style="width:${c.box[2] * 1.5}px;height:${c.box[3] * 1.5}px"><use href="#gl-${c.name}"/></svg><code>${c.name}</code></li>`).join("");
  const radii = Object.entries(TOKENS.radius).map(([k, v]) =>
    `<li><span class="rad" style="border-radius:${Math.min(v.$value, 40)}px"></span><code>${k}</code><small>${v.$value}px</small></li>`).join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glow UI framework</title>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;700&family=Libre+Caslon+Display&family=Libre+Caslon+Text:ital@1&display=swap" rel="stylesheet">
<link rel="stylesheet" href="framework/glow.css"><link rel="stylesheet" href="framework/docs.css"></head>
<body>${SPRITE}<main>
<p class="crumb"><a href="/">← Live site</a> <a href="/design">Design notes</a> <a href="framework/tokens.json">tokens.json</a> <a href="framework/glow.css">glow.css</a></p>
<h1 class="gl-display-xl" style="font-family:'Libre Caslon Display',Georgia,serif">Glow UI framework</h1>
<p class="lede gl-body-l">Design tokens, components, icons and fonts measured from the original Glow design. The website, the Affinity build and the PhotoCraft build all read the same <code>tokens.json</code>, so colours, type, radii and icons stay identical everywhere.</p>

<h2>Colour</h2><ul class="swatches">${swatches}</ul>
<h2>Type</h2><p class="note">Display text uses <b>Glow Display</b>, a font traced from the design's own lettering with kerning measured from the design. It covers the headline's letters plus the badge's <code>0 1 +</code>; other display text falls back to Libre Caslon Display. Body text is Figtree, the closest match the font finder found.</p><ul class="types">${types}</ul>
<h2>Radius</h2><ul class="radii">${radii}</ul>

<h2>Buttons &amp; pills</h2>
<div class="row"><a class="gl-btn" href="#">Sign Up / Log In</a><button class="gl-btn gl-btn--square" type="button">Search</button><button class="gl-pill" type="button"><svg class="gl-icon" style="width:16px;height:20px"><use href="#gl-nav_pin"/></svg>Sydney, Australia<svg class="gl-icon" style="width:12px;height:8px"><use href="#gl-nav_chevron"/></svg></button><a class="gl-btn gl-btn--sm" href="#">Book</a></div>

<h2>Search bar</h2>
<form class="gl-search" role="search" onsubmit="event.preventDefault()">
  <label class="gl-search__field"><svg class="gl-icon"><use href="#gl-search_icon"/></svg><input placeholder="Search services or treatments" aria-label="Search services or treatments"></label>
  <label class="gl-search__field"><svg class="gl-icon" style="width:18px"><use href="#gl-search_pin"/></svg><select aria-label="Location"><option>Sydney, Australia</option></select></label>
  <button class="gl-btn gl-btn--square" type="submit">Search</button>
</form>

<h2>Features</h2>
<ul class="gl-features" role="list">
  <li class="gl-feature"><span class="gl-ring"><svg class="gl-icon" style="width:29px;height:31px"><use href="#gl-feat_search"/></svg></span><span class="gl-title">Search</span><span class="gl-label">Find the perfect<br>service</span></li>
  <li class="gl-feature"><span class="gl-ring"><svg class="gl-icon" style="width:29px;height:29px"><use href="#gl-feat_book"/></svg></span><span class="gl-title">Book</span><span class="gl-label">Instant booking<br>in seconds</span></li>
  <li class="gl-feature"><span class="gl-ring"><svg class="gl-icon" style="width:30px;height:28px"><use href="#gl-feat_enjoy"/></svg></span><span class="gl-title">Enjoy</span><span class="gl-label">Feel amazing,<br>every time</span></li>
  <li class="gl-feature"><span class="gl-ring"><svg class="gl-icon" style="width:29px;height:33px"><use href="#gl-feat_trusted"/></svg></span><span class="gl-title">Trusted</span><span class="gl-label">Verified reviews<br>you can trust</span></li>
</ul>

<h2>App components</h2>
<div class="row app">
  <div class="tiles">${["facials", "nails", "brows", "hair", "makeup"].map((t) => { const c = MANIFEST.find((m) => m.name === "tile_" + t);
    return `<div class="gl-tile"><svg class="gl-icon" style="width:${c.box[2]}px;height:${c.box[3]}px"><use href="#gl-${c.name}"/></svg>${t[0].toUpperCase() + t.slice(1)}</div>`; }).join("")}</div>
  <article class="gl-card" style="width:270px"><img class="gl-card__thumb" src="assets/thumb_facial_hd-2x.jpg" alt="Woman relaxing during a facial"><div><h4 class="gl-card__title">The Facial Room</h4><p class="gl-card__meta">★ 4.9 (128) · Surry Hills</p><p class="gl-card__svc">Signature Glow Facial</p><p class="gl-card__price">$149</p></div><svg class="gl-card__save"><use href="#gl-card_bookmark"/></svg><a class="gl-btn gl-btn--sm" href="#">Book</a></article>
  <nav class="gl-tabbar" style="width:300px" aria-label="Example tab bar">${[["home", "Home"], ["search", "Search"], ["bookings", "Bookings"], ["favourites", "Favourites"], ["profile", "Profile"]].map(([n, l], i) => {
    const c = MANIFEST.find((m) => m.name === "tab_" + n);
    return `<span${i === 0 ? ' aria-current="page"' : ""}><svg class="gl-icon" style="width:${c.box[2]}px;height:${c.box[3]}px"><use href="#gl-${c.name}"/></svg>${l}</span>`; }).join("")}</nav>
  <div class="gl-badge"><span style="margin:0">TRUSTED BY</span><strong style="font-family:var(--serif-alt, 'Libre Caslon Display')">1000+</strong><span>HAPPY CLIENTS</span></div>
</div>

<h2>Icons</h2><p class="note">Traced from the design with <code>tools/slicer.py</code> (potrace at 8×). Each is a <code>&lt;symbol id="gl-NAME"&gt;</code> in <a href="framework/icons.svg">icons.svg</a>; colour follows CSS <code>color</code>.</p><ul class="icons">${iconList}</ul>
<h2>Brand logos</h2><p class="note">Split out of the logo strip into separate vector components. Third-party trademarks: get permission before using them.</p>${LOGOS.replace('class="logos"', 'class="gl-logos"')}
</main></body></html>`;
}

const DOCS_CSS = `*{box-sizing:border-box;margin:0;padding:0}body{background:var(--gl-canvas);color:var(--gl-ink);font-family:var(--gl-font-sans);-webkit-font-smoothing:antialiased}
main{max-width:1100px;margin:0 auto;padding:32px 16px 80px}a{color:inherit}ul{list-style:none}code{font:12px ui-monospace,Menlo,monospace;color:#444}
.crumb{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:14px;margin-bottom:28px}.lede{max-width:760px;margin-top:12px}
h2{font:600 18px var(--gl-font-sans);margin:44px 0 14px}.note{color:var(--gl-text-muted);font-size:14px;max-width:760px;margin-bottom:14px}
.swatches{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}.swatches li{display:grid;grid-template-columns:44px 1fr;gap:2px 10px;align-items:center;background:#fff;border:1px solid var(--gl-line);border-radius:10px;padding:10px}
.sw{grid-row:span 3;width:44px;height:44px;border-radius:8px;border:1px solid rgba(0,0,0,.08)}.swatches small,.types small,.radii small{color:var(--gl-text-subtle);font-size:12px}
.types li{display:grid;gap:4px;padding:14px 0;border-bottom:1px solid var(--gl-line)}.types span{line-height:1.15;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.radii{display:flex;flex-wrap:wrap;gap:16px}.radii li{display:grid;justify-items:center;gap:4px}.rad{width:72px;height:56px;background:#fff;border:1px solid var(--gl-line)}
.row{display:flex;flex-wrap:wrap;gap:16px;align-items:center}.app{align-items:flex-start}.tiles{display:flex;gap:7px}
.icons{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}.icons li{display:grid;justify-items:center;gap:8px;background:#fff;border:1px solid var(--gl-line);border-radius:10px;padding:14px 6px}.icons .gl-icon{color:var(--gl-ink)}
.gl-logos{background:var(--gl-strip);border:1px solid var(--gl-line);border-radius:12px;padding:24px}`;

rmSync("dist", { recursive: true, force: true });
for (const key of Object.keys(VARIANTS)) {
  const out = `dist/${key}`;
  mkdirSync(`${out}/design`, { recursive: true });
  cpSync("src", out, { recursive: true });
  cpSync(`variants/${key}/assets`, `${out}/assets`, { recursive: true });
  cpSync("framework", `${out}/framework`, { recursive: true });
  mkdirSync(`${out}/framework/fonts`, { recursive: true });
  for (const f of readdirSync("fonts/out")) if (f.endsWith(".woff2") || f.endsWith(".otf")) cpSync(`fonts/out/${f}`, `${out}/framework/fonts/${f}`);
  mkdirSync(`${out}/framework/logos`, { recursive: true });
  for (const c of brands) cpSync(`variants/shared/components/${c.svg}`, `${out}/framework/logos/${c.svg}`);
  writeFileSync(`${out}/framework/icons.svg`, SPRITE.replace(' style="display:none"', ""));
  writeFileSync(`${out}/framework/docs.css`, DOCS_CSS);
  writeFileSync(`${out}/framework.html`, frameworkPage());
  cpSync(`variants/${key}/render.jpg`, `${out}/design/render.jpg`);
  cpSync("variants/shared/original.jpg", `${out}/design/original.jpg`);
  if (existsSync(`variants/${key}/render-v2.jpg`)) cpSync(`variants/${key}/render-v2.jpg`, `${out}/design/render-v2.jpg`);
  writeFileSync(`${out}/design.html`, designPage(key));
  writeFileSync(`${out}/design.css`, DESIGN_CSS);
  writeFileSync(`${out}/404.html`, NOT_FOUND);
  const html = readFileSync(`${out}/index.html`, "utf8")
    .replace("<!--icons-->", SPRITE)
    .replace("<!--logos-->", LOGOS)
    .replace("<!--made-with-->", `<a href="/design">How this page was made (${VARIANTS[key].name})</a> · <a href="/framework">Glow UI framework</a>`);
  writeFileSync(`${out}/index.html`, html);
  console.log("built", out);
}
