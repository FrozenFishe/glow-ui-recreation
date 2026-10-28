// Fluttering Penguins worker: static site (ASSETS) plus two form endpoints stored in KV (FORMS).
//   POST /api/pledge     donation pledge  -> key pledge:<iso time>:<id>
//   POST /api/subscribe  newsletter       -> key sub:<email>
// Read them with: npx wrangler kv key list --binding FORMS -c wrangler.jsonc --remote
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
const str = (v, n) => (typeof v === "string" ? v.trim().slice(0, n) : "");

async function limited(env, ip) {  // at most 8 submissions per IP per 10 minutes
  const k = `rl:${ip}`, n = Number((await env.FORMS.get(k)) || 0);
  if (n >= 8) return true;
  await env.FORMS.put(k, String(n + 1), { expirationTtl: 600 });
  return false;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(req);
    if (req.method !== "POST") return json({ error: "method" }, 405);
    const origin = req.headers.get("origin");
    if (origin && new URL(origin).host !== url.host) return json({ error: "origin" }, 403);
    if (Number(req.headers.get("content-length") || 0) > 4096) return json({ error: "size" }, 413);
    let b;
    try { b = await req.json(); } catch { return json({ error: "json" }, 400); }
    if (b.website) return json({ ok: true, id: "FP-" + crypto.randomUUID().slice(0, 8).toUpperCase() });  // honeypot
    const ip = req.headers.get("cf-connecting-ip") || "0";
    if (await limited(env, ip)) return json({ error: "rate" }, 429);
    const at = new Date().toISOString(), lang = b.lang === "en" ? "en" : "ko";
    if (url.pathname === "/api/pledge") {
      const amount = Math.round(Number(b.amount));
      const p = { type: b.type === "once" ? "once" : "monthly", amount, name: str(b.name, 60), email: str(b.email, 120),
        phone: str(b.phone, 30), message: str(b.message, 500), lang, at, country: req.cf?.country || "" };
      if (!p.name || !EMAIL.test(p.email) || !(amount >= 1000 && amount <= 100000000)) return json({ error: "invalid" }, 400);
      const id = "FP-" + crypto.randomUUID().slice(0, 8).toUpperCase();
      await env.FORMS.put(`pledge:${at}:${id}`, JSON.stringify({ id, ...p }), { metadata: { amount, type: p.type } });
      return json({ ok: true, id });
    }
    if (url.pathname === "/api/subscribe") {
      const email = str(b.email, 120).toLowerCase();
      if (!EMAIL.test(email)) return json({ error: "invalid" }, 400);
      await env.FORMS.put(`sub:${email}`, JSON.stringify({ email, lang, at }));
      return json({ ok: true });
    }
    return json({ error: "not found" }, 404);
  },
};
