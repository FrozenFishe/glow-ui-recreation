// Fluttering Penguins: language switch (ko/en), mobile menu, scroll highlight, stat counters, donate dialog and forms.
(function () {
  "use strict";
  var EN = {
    skip: "Skip to content", menu: "Menu", mainNav: "Main", footNav: "Footer", lang: "Language", close: "Close",
    "nav.home": "Home", "nav.about": "About", "nav.work": "Our work", "nav.support": "Support", "nav.news": "News",
    "cta.donate": "Donate now", "cta.about": "About us", "cta.story": "Read our story", "cta.join": "Join us",
    "hero.eyebrow": "Small hearts make a big difference",
    "hero.title": "Fluttering Penguins is <br>protecting more lives, <br>right now.",
    "hero.lead": "We are a Korean non-profit protecting penguins and their habitats from climate change, <br>and working for a sustainable planet.",
    "mission.title": "What we do",
    "mission.lead": "Fluttering Penguins works on penguin protection, climate action <br>and a sustainable environment.",
    "m1.t": "Penguin protection", "m1.d": "We protect the habitats of endangered penguins <br>and help their numbers recover.",
    "m2.t": "Climate action", "m2.d": "We run environmental campaigns and education <br>to reduce the impact of global warming.",
    "m3.t": "Community", "m3.d": "We strengthen partnerships with local communities <br>for a sustainable future.",
    "m4.t": "Education & awareness", "m4.d": "We run environmental education and awareness programmes <br>to leave a better planet for the next generation.",
    "impact.title": "Change we make together",
    "impact.lead": "Thanks to the love and support of so many people, here is what we have achieved so far.",
    s1: "Penguins protected", s2: "Protected areas created", s3: "Donors", s4: "Of donations used for our work",
    "story.title": "Small wings, a big world",
    "story.lead": "Fluttering Penguins is a non-profit founded in Korea, <br>working every day for the future of penguins and our planet. <br>The small things we do together can protect many more lives.",
    "story.alt": "An emperor penguin chick looking up at the sky",
    "promise.title": "Our promise",
    "promise.1": "We protect the habitats of endangered penguins and help their populations recover.",
    "promise.2": "We keep running campaigns and education to reduce the impact of climate change.",
    "promise.3": "We build a sustainable future together with local communities.",
    "promise.4": "Every donation goes to our work for penguins and the planet.",
    "news.title": "Get penguin news", "news.lead": "Updates on our work and campaigns, by email.", "news.cta": "Subscribe",
    "foot.about": "A Korean non-profit protecting penguins and our planet", "foot.replica": "1:1 design replica",
    "d.title": "Become a supporter", "d.lead": "Send us this form and our team will email you how to complete your donation.",
    "d.type": "Donation type", "d.monthly": "Monthly", "d.once": "One-time", "d.amount": "Amount", "d.custom": "Other",
    "d.customAmt": "Amount (KRW)", "d.submit": "Send my pledge", "d.thanks": "Thank you!",
    "d.thanksLead": "We have received your pledge and will email you shortly.",
    "form.name": "Name", "form.email": "Email", "form.phone": "Phone (optional)", "form.msg": "Message of support (optional)",
    "form.consent": "I agree to the collection and use of my details so you can contact me about my donation.",
    "err.email": "Please enter a valid email address.", "err.name": "Please enter your name.", "err.consent": "Please agree to the privacy notice.",
    "err.amount": "Please enter an amount of at least 1,000 KRW.", "err.server": "Something went wrong. Please try again.",
    "ok.sub": "Subscribed! Thanks for following our news.", "sending": "Sending…", "ref": "Reference"
  };
  var KO_ERR = {
    "err.email": "올바른 이메일 주소를 입력해 주세요.", "err.name": "이름을 입력해 주세요.", "err.consent": "개인정보 수집·이용에 동의해 주세요.",
    "err.amount": "1,000원 이상의 금액을 입력해 주세요.", "err.server": "문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    "ok.sub": "구독해 주셔서 감사합니다!", "sending": "보내는 중…", "ref": "접수 번호"
  };
  var KO = {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  $$("[data-i18n]").forEach(function (el) { KO[el.dataset.i18n] = el.textContent; });
  $$("[data-i18n-html]").forEach(function (el) { KO[el.dataset.i18nHtml] = el.innerHTML; });
  $$("[data-i18n-label]").forEach(function (el) { KO[el.dataset.i18nLabel] = el.getAttribute("aria-label") || ""; });
  $$("[data-i18n-alt]").forEach(function (el) { KO[el.dataset.i18nAlt] = el.alt; });
  var lang = "ko";
  function t(k) { return (lang === "en" ? EN[k] : (KO[k] || KO_ERR[k])) || KO_ERR[k] || k; }
  function setLang(l) {
    lang = l === "en" ? "en" : "ko";
    document.documentElement.lang = lang;
    $$("[data-i18n]").forEach(function (el) { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-html]").forEach(function (el) { el.innerHTML = t(el.dataset.i18nHtml); });
    $$("[data-i18n-label]").forEach(function (el) { el.setAttribute("aria-label", t(el.dataset.i18nLabel)); });
    $$("[data-i18n-alt]").forEach(function (el) { el.alt = t(el.dataset.i18nAlt); });
    $("#lang").value = lang;
    document.title = lang === "en" ? "Fluttering Penguins | A non-profit protecting penguins and our planet" : "Fluttering Penguins | 펭귄과 지구를 지키는 비영리 단체";
    try { localStorage.setItem("fp-lang", lang); } catch (e) {}
  }
  var saved = new URLSearchParams(location.search).get("lang");
  if (!saved) { try { saved = localStorage.getItem("fp-lang"); } catch (e) {} }
  if (saved === "en") setLang("en");
  $("#lang").addEventListener("change", function () { setLang(this.value); });

  // mobile menu
  var burger = $(".burger"), menu = $("#menu");
  burger.addEventListener("click", function () {
    var open = menu.classList.toggle("open");
    burger.setAttribute("aria-expanded", open);
  });
  $$("#menu a").forEach(function (a) { a.addEventListener("click", function () { menu.classList.remove("open"); burger.setAttribute("aria-expanded", "false"); }); });

  // highlight the section in view
  var links = $$("[data-spy]");
  function spy() {
    var y = scrollY + innerHeight * 0.35, cur = "top";
    links.forEach(function (a) { var s = document.getElementById(a.dataset.spy); if (s && s.id !== "top" && s.getBoundingClientRect().top + scrollY <= y) cur = a.dataset.spy; });
    if (innerHeight + scrollY >= document.body.scrollHeight - 4) cur = "news";
    links.forEach(function (a) { a.classList.toggle("on", a.dataset.spy === cur); if (a.dataset.spy === cur) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
  }
  addEventListener("scroll", spy, { passive: true }); spy();

  // count the stats up when they come into view
  var nums = $$("[data-count]"), reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if ("IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        var el = e.target, end = +el.dataset.count, suf = el.dataset.suffix || "", t0 = performance.now();
        (function step(now) {
          var p = Math.min((now - t0) / 1200, 1), v = Math.round(end * (1 - Math.pow(1 - p, 3)));
          el.textContent = v.toLocaleString("en-US") + suf;
          if (p < 1) requestAnimationFrame(step);
        })(t0);
      });
    }, { threshold: 0.6 });
    nums.forEach(function (n) { io.observe(n); });
  }

  // story: expand our promise
  var sb = $("#storyBtn"), pr = $("#promise");
  sb.addEventListener("click", function () {
    var open = pr.hidden; pr.hidden = !open; sb.setAttribute("aria-expanded", open);
    if (open) pr.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
  });

  // donate dialog
  var dlg = $("#donate"), form = $("#donateForm"), done = $(".d-done"), formWrap = $(".d-form");
  function openDonate() {
    formWrap.hidden = false; done.hidden = true; $(".msg", form).textContent = "";
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    setTimeout(function () { $("[name=name]", form).focus(); }, 30);
  }
  $$("[data-donate]").forEach(function (b) { b.addEventListener("click", openDonate); });
  if (location.hash === "#donate") openDonate();
  dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });
  var custom = $(".custom", form);
  $$("[name=amount]", form).forEach(function (r) { r.addEventListener("change", function () { custom.hidden = r.value !== "custom" || !r.checked; if (!custom.hidden) $("input", custom).focus(); }); });

  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  function post(url, data) {
    return fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(data) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) throw j; return j; }); });
  }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var f = new FormData(form), msg = $(".msg", form), btn = $("[type=submit]", form);
    var amount = f.get("amount") === "custom" ? Number(f.get("customAmount")) : Number(f.get("amount"));
    var err = !String(f.get("name") || "").trim() ? "err.name" : !EMAIL.test(f.get("email") || "") ? "err.email"
      : !(amount >= 1000) ? "err.amount" : !f.get("consent") ? "err.consent" : "";
    if (err) { msg.className = "msg err"; msg.textContent = t(err); return; }
    btn.disabled = true; msg.className = "msg"; msg.textContent = t("sending");
    post("/api/pledge", { type: f.get("type"), amount: amount, name: f.get("name"), email: f.get("email"), phone: f.get("phone"),
      message: f.get("message"), website: f.get("website"), lang: lang })
      .then(function (j) {
        formWrap.hidden = true; done.hidden = false; form.reset(); custom.hidden = true;
        $(".ref", done).textContent = t("ref") + ": " + j.id;
      })
      .catch(function () { msg.className = "msg err"; msg.textContent = t("err.server"); })
      .then(function () { btn.disabled = false; });
  });

  // newsletter
  var sub = $("#subForm");
  sub.addEventListener("submit", function (e) {
    e.preventDefault();
    var msg = $(".msg", sub), email = sub.email.value.trim();
    if (!EMAIL.test(email)) { msg.className = "msg err"; msg.textContent = t("err.email"); return; }
    msg.className = "msg"; msg.textContent = t("sending");
    post("/api/subscribe", { email: email, website: sub.website.value, lang: lang })
      .then(function () { msg.textContent = t("ok.sub"); sub.reset(); })
      .catch(function () { msg.className = "msg err"; msg.textContent = t("err.server"); });
  });
})();
