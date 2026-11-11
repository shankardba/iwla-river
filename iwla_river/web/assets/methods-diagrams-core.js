/* Core method diagrams: pairing, holding things equal, each site against itself, resampling, shuffling.
   The dots are illustrative (seeded), shaped like the real data; the real numbers are in each finding's card. */
"use strict";
(() => {
const { el, rng, lerp, fit, pct, frame } = window.SOS;
const D = (window.SOS_DIAGRAMS = window.SOS_DIAGRAMS || {});

// ---------------------------------------------------------------- 1. Pairing in time and space
D.pairing = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 330");
  const r = rng(11);
  const x0 = 110, w = 580, T = (d) => x0 + (d / 365) * w;   // one year across
  const rows = [70, 160, 250];
  const g = el("g", {}, svg);
  ["Site A", "Site B", "Site C"].forEach((s, i) => {
    el("text", { x: 20, y: rows[i] + 5, class: "lbl b", text: s }, g);
    el("line", { x1: x0, x2: x0 + w, y1: rows[i], y2: rows[i], class: "ax" }, g);
  });
  ["Jan", "Apr", "Jul", "Oct"].forEach((m, k) => el("text", { x: T(k * 91), y: 312, class: "tick", "text-anchor": "middle", text: m }, g));
  el("text", { x: x0, y: 30, class: "lbl m", text: "▲ bug survey   ● chloride reading (Salt Watch strip or lab)" }, g);
  // surveys and readings per site
  const surveys = [[40, 200, 300], [120, 260], [90, 180, 330]];
  const reads = rows.map((_, i) => Array.from({ length: 9 }, () => Math.round(r() * 360)).concat(surveys[i].map((d) => d + Math.round((r() - 0.5) * 10))));
  const win = el("g", { opacity: 0 }, svg);
  const pairs = [];
  const sv = [];
  rows.forEach((y, i) => {
    reads[i].forEach((d) => el("circle", { cx: T(d), cy: y + 18, r: 5, class: "pt2" }, g));
    surveys[i].forEach((d) => {
      const tri = el("path", { d: `M${T(d)} ${y - 18} l-7 12 h14 z`, class: "pt" }, g);
      const band = el("rect", { x: T(d - 7), y: y - 26, width: T(14) - x0, height: 52, class: "band", opacity: 0, rx: 4 }, win);
      const hit = reads[i].filter((q) => Math.abs(q - d) <= 7);
      sv.push({ band, hit: hit.length > 0, tri });
      hit.forEach((q) => pairs.push(el("line", { x1: T(d), y1: y - 6, x2: T(q), y2: y + 13, class: "fit", "stroke-width": 2, opacity: 0 }, svg)));
    });
  });
  const cov = el("text", { x: x0, y: 52, class: "lbl acc", opacity: 0, text: "" }, svg);
  return [
    { cap: "Each site has <b>bug surveys</b> (triangles) and <b>chloride readings</b> (dots) taken on their own schedules. They rarely fall on the same day.", play: async () => {} },
    { cap: "Pairing rule: a survey takes the <b>median chloride read within 7 days</b> at the same site. The shaded windows show where each survey looks.", play: async (h) => {
      win.setAttribute("opacity", 1);
      await h.tween(900, (t) => sv.forEach((s) => s.band.setAttribute("opacity", t)));
    } },
    { cap: "Surveys with a reading inside their window are <b>paired</b>; the rest drop out of this analysis.", play: async (h) => {
      await h.tween(900, (t) => { pairs.forEach((p) => p.setAttribute("opacity", t)); sv.forEach((s) => { if (!s.hit) s.tri.setAttribute("opacity", 1 - 0.75 * t); }); });
    } },
    { cap: "Coverage comes first: in the real data only <b>644 of 7,296 surveys (8.8%)</b> at 236 sites paired. Paired surveys score differently from the rest, so every result says which rows it stands for.", hold: 2600, play: async (h) => {
      const n = sv.filter((s) => s.hit).length;
      cov.textContent = `Here: ${n} of ${sv.length} surveys paired`;
      await h.tween(500, (t) => cov.setAttribute("opacity", t));
    } },
  ];
};

// ---------------------------------------------------------------- 2. Holding things equal
function saltData(seed, nSites = 60, visits = 4) {
  const r = rng(seed); const pts = [];
  for (let s = 0; s < nSites; s++) {
    const paved = r() * 40;                                   // % of the watershed paved
    const siteCl = 1.0 + 0.035 * paved + r.norm() * 0.25;     // paving brings salt
    const level = 0.62 - 0.009 * paved + r.norm() * 0.05;     // paving lowers the share (not the salt itself)
    for (let v = 0; v < visits; v++) {
      const cl = siteCl + r.norm() * 0.18;
      pts.push({ s, paved, x: cl, y: Math.min(0.95, Math.max(0.02, level - 0.02 * (cl - siteCl) + r.norm() * 0.05)) });
    }
  }
  return pts;
}

D.holdequal = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 400");
  const pts = saltData(5);
  const F = frame(svg, { x0: 80, y0: 24, w: 600, h: 300, xd: [0.4, 3.0], yd: [0, 1], xl: "chloride (log scale: 3, 10, 30, 100, 300 mg/L)", yl: "share of sensitive animals",
    xt: [[0.5, "3"], [1, "10"], [1.5, "30"], [2, "100"], [2.5, "300"]], yt: [[0, "0"], [0.5, "0.5"], [1, "1"]] });
  const band = (p) => (p < 13 ? 0 : p < 27 ? 1 : 2);
  const cols = ["var(--c3)", "var(--c2)", "var(--bad)"];
  const dots = pts.map((p) => el("circle", { cx: F.X(p.x), cy: F.Y(p.y), r: 4, class: "pt" }, svg));
  const all = fit(pts.map((p) => p.x), pts.map((p) => p.y));
  const line = (f, cls, x1 = 0.6, x2 = 2.8) => el("line", { x1: F.X(x1), y1: F.Y(f.a + f.b * x1), x2: F.X(x2), y2: F.Y(f.a + f.b * x2), class: cls, opacity: 0 }, svg);
  const raw = line(all, "fit");
  const groups = [0, 1, 2].map((b) => pts.filter((p) => band(p.paved) === b));
  const fits = groups.map((g) => fit(g.map((p) => p.x), g.map((p) => p.y)));
  // a common slope within paving bands (what "holding paving equal" estimates)
  let sxy = 0, sxx = 0;
  groups.forEach((g, k) => g.forEach((p) => { sxy += (p.x - fits[k].mx) * (p.y - fits[k].my); sxx += (p.x - fits[k].mx) ** 2; }));
  const common = sxy / sxx;
  const within = fits.map((f, k) => {
    const xs = groups[k].map((p) => p.x); const lo = Math.min(...xs), hi = Math.max(...xs);
    return line({ a: f.my - common * f.mx, b: common }, "fit", lo, hi);
  });
  within.forEach((l, k) => l.setAttribute("style", `stroke:${cols[k]}`));
  const key = el("g", { opacity: 0 }, svg);
  ["little paving (<13%)", "some (13–27%)", "a lot (>27%)"].forEach((t, k) => {
    el("circle", { cx: 440, cy: 40 + k * 20, r: 5, style: `fill:${cols[k]}` }, key);
    el("text", { x: 452, y: 45 + k * 20, class: "lbl", text: t }, key);
  });
  const note = el("text", { x: 90, y: 395, class: "lbl acc", opacity: 0, text: "" }, svg);
  return [
    { cap: "Each dot is a survey: chloride around that visit, and the share of animals that need clean water. Saltier water, fewer sensitive animals?", play: async () => {} },
    { cap: `A straight-line fit (least squares) gives the <b>raw slope</b>: the share falls about ${Math.abs(all.b).toFixed(2)} for each tenfold rise in chloride.`, play: async (h) => { await h.tween(700, (t) => raw.setAttribute("opacity", t)); } },
    { cap: "But saltier streams are also in <b>more paved watersheds</b>, and paving harms streams in other ways (heat, flashy flows, sediment). Colour the dots by paving.", play: async (h) => {
      await h.tween(900, (t) => { dots.forEach((d, i) => d.setAttribute("style", `fill:${cols[band(pts[i].paved)]};fill-opacity:${0.7}`)); key.setAttribute("opacity", t); });
    } },
    { cap: `<b>Holding paving equal</b> means comparing saltier and less salty streams <i>within</i> the same paving level. The slope shrinks to ${Math.abs(common).toFixed(2)}: most of the raw link was paving.`, hold: 2400, play: async (h) => {
      await h.tween(900, (t) => { raw.setAttribute("opacity", 1 - 0.75 * t); within.forEach((l) => l.setAttribute("opacity", t)); });
      note.textContent = `raw ${all.b.toFixed(2)} → paving held equal ${common.toFixed(2)}`;
      await h.tween(400, (t) => note.setAttribute("opacity", t));
    } },
    { cap: "The real model holds <b>paving, season, state and survey form</b> equal at once (multiple regression), and treats each site's repeat visits as one cluster so they don't count as independent evidence.", play: async () => {} },
  ];
};

// ---------------------------------------------------------------- 3. Each site against itself
D.within = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 400");
  const pts = saltData(9, 14, 6);
  const F = frame(svg, { x0: 80, y0: 24, w: 600, h: 300, xd: [0.4, 3.0], yd: [0, 1], xl: "chloride (log scale)", yl: "share of sensitive animals",
    xt: [[0.5, "3"], [1, "10"], [1.5, "30"], [2, "100"], [2.5, "300"]], yt: [[0, "0"], [0.5, "0.5"], [1, "1"]] });
  const pal = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)"];
  const dots = pts.map((p) => el("circle", { cx: F.X(p.x), cy: F.Y(p.y), r: 4.5, class: "pt" }, svg));
  const all = fit(pts.map((p) => p.x), pts.map((p) => p.y));
  const between = el("line", { x1: F.X(0.7), y1: F.Y(all.a + all.b * 0.7), x2: F.X(2.7), y2: F.Y(all.a + all.b * 2.7), class: "fit", opacity: 0 }, svg);
  const sites = [...new Set(pts.map((p) => p.s))];
  // pooled within-site slope: each site's own cloud, centred on itself
  let sxy = 0, sxx = 0; const lines = [];
  sites.forEach((s) => {
    const g = pts.filter((p) => p.s === s); const f = fit(g.map((p) => p.x), g.map((p) => p.y));
    g.forEach((p) => { sxy += (p.x - f.mx) * (p.y - f.my); sxx += (p.x - f.mx) ** 2; });
    lines.push({ s, f, lo: Math.min(...g.map((p) => p.x)), hi: Math.max(...g.map((p) => p.x)) });
  });
  const w = sxy / sxx;
  const wl = lines.map((L, k) => el("line", { x1: F.X(L.lo), y1: F.Y(L.f.my + w * (L.lo - L.f.mx)), x2: F.X(L.hi), y2: F.Y(L.f.my + w * (L.hi - L.f.mx)), class: "fit acc", "stroke-width": 2.5, opacity: 0, style: `stroke:${pal[k % 4]}` }, svg));
  const note = el("text", { x: 90, y: 395, class: "lbl acc", opacity: 0, text: `between sites ${all.b.toFixed(2)} · within a site ${w.toFixed(2)}` }, svg);
  return [
    { cap: "Fourteen sites, six visits each. Across sites, saltier streams hold fewer sensitive animals.", play: async (h) => { await h.tween(600, (t) => between.setAttribute("opacity", t)); } },
    { cap: "Colour the visits by site: each site is its own little cloud. Sites differ in many fixed ways (geology, shade, paving) that also differ with salt.", play: async (h) => {
      await h.tween(800, () => dots.forEach((d, i) => d.setAttribute("style", `fill:${pal[sites.indexOf(pts[i].s) % 4]}`)));
    } },
    { cap: "<b>Compare each site only with itself</b>: on visits when <i>this</i> stream was saltier, did it have fewer sensitive animals than on its own fresher visits? Fixed differences between sites cancel out.", play: async (h) => {
      await h.tween(900, (t) => { wl.forEach((l) => l.setAttribute("opacity", t)); between.setAttribute("opacity", 1 - 0.7 * t); });
    } },
    { cap: "Here the link <b>vanishes within a site</b>: it lives between sites. That is what the real data showed for the sensitive share, so the engine calls the link <b>hinted</b>, not supported: saltier <i>places</i> differ, but a salt pulse at one place doesn't clearly drop the share.", hold: 2800, play: async (h) => { await h.tween(400, (t) => note.setAttribute("opacity", t)); } },
  ];
};

// ---------------------------------------------------------------- 4. Resampling whole sites (bootstrap interval)
D.bootstrap = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 420");
  const pts = saltData(21, 40, 3);
  const F = frame(svg, { x0: 80, y0: 24, w: 400, h: 300, xd: [0.4, 3.0], yd: [0, 1], xl: "chloride (log)", yl: "sensitive share",
    xt: [[0.5, "3"], [1.5, "30"], [2.5, "300"]], yt: [[0, "0"], [0.5, "0.5"], [1, "1"]] });
  pts.forEach((p) => el("circle", { cx: F.X(p.x), cy: F.Y(p.y), r: 3.5, class: "pt", "fill-opacity": 0.35 }, svg));
  const r = rng(4); const sites = [...new Set(pts.map((p) => p.s))];
  const bySite = sites.map((s) => pts.filter((p) => p.s === s));
  const B = 120, slopes = [];
  const fan = el("g", {}, svg);
  const lines = [];
  for (let b = 0; b < B; b++) {
    const pick = []; for (let k = 0; k < sites.length; k++) pick.push(...bySite[Math.floor(r() * sites.length)]);
    const f = fit(pick.map((p) => p.x), pick.map((p) => p.y)); slopes.push(f.b);
    lines.push(el("line", { x1: F.X(0.6), y1: F.Y(f.a + f.b * 0.6), x2: F.X(2.8), y2: F.Y(f.a + f.b * 2.8), class: "fit thin", opacity: 0 }, fan));
  }
  const real = fit(pts.map((p) => p.x), pts.map((p) => p.y));
  el("line", { x1: F.X(0.6), y1: F.Y(real.a + real.b * 0.6), x2: F.X(2.8), y2: F.Y(real.a + real.b * 2.8), class: "fit acc" }, svg);
  // histogram of slopes
  const hx0 = 520, hw = 170, hy = 324, lo = Math.min(...slopes), hi = Math.max(...slopes), nb = 14;
  const bins = new Array(nb).fill(0);
  const bi = (v) => Math.min(nb - 1, Math.floor(((v - lo) / (hi - lo + 1e-9)) * nb));
  el("line", { x1: hx0, x2: hx0 + hw, y1: hy, y2: hy, class: "ax" }, svg);
  el("text", { x: hx0 + hw / 2, y: hy + 36, class: "axl", "text-anchor": "middle", text: "slope from each resample" }, svg);
  const bars = bins.map((_, k) => el("rect", { x: hx0 + (k * hw) / nb + 1, width: hw / nb - 2, y: hy, height: 0, class: "bar" }, svg));
  const L = pct(slopes, 0.025), H = pct(slopes, 0.975);
  const X = (v) => hx0 + ((v - lo) / (hi - lo)) * hw;
  const ci = el("g", { opacity: 0 }, svg);
  el("line", { x1: X(L), x2: X(H), y1: hy + 12, y2: hy + 12, class: "fit", "stroke-width": 4 }, ci);
  el("text", { x: X(L), y: hy + 56, class: "lbl hi", "text-anchor": "middle", text: L.toFixed(2) }, ci);
  el("text", { x: X(H), y: hy + 56, class: "lbl hi", "text-anchor": "middle", text: H.toFixed(2) }, ci);
  el("text", { x: hx0 + hw / 2, y: hy + 78, class: "lbl b", "text-anchor": "middle", text: "95% interval: middle 95%" }, ci);
  const count = el("text", { x: hx0, y: 40, class: "lbl m", text: "" }, svg);
  return [
    { cap: `40 sites, three visits each, and the fitted slope (${real.b.toFixed(2)}). How sure is that number? A different set of sites would give a slightly different slope.`, play: async () => {} },
    { cap: "<b>Resample whole sites</b>: draw 40 sites at random <i>with replacement</i> (some twice, some not at all), keeping each site's visits together, and fit again. Repeat.", play: async (h) => {
      for (let b = 0; b < 12; b++) { lines[b].setAttribute("opacity", 1); bars[bi(slopes[b])].setAttribute("height", (+bars[bi(slopes[b])].getAttribute("height") || 0) + 6); bars[bi(slopes[b])].setAttribute("y", hy - +bars[bi(slopes[b])].getAttribute("height")); count.textContent = `resamples: ${b + 1}`; await h.wait(180); }
    } },
    { cap: "After many resamples the slopes pile up into a spread. Whole sites move together because a site's visits share its fixed traits: resampling single visits would look falsely sure.", play: async (h) => {
      const done = new Array(nb).fill(0); for (let b = 0; b < 12; b++) done[bi(slopes[b])]++;
      await h.tween(1400, (t) => {
        const upto = Math.round(lerp(12, B, t));
        const c = new Array(nb).fill(0); for (let b = 0; b < upto; b++) { c[bi(slopes[b])]++; lines[b].setAttribute("opacity", 1); }
        c.forEach((v, k) => { bars[k].setAttribute("height", v * 6); bars[k].setAttribute("y", hy - v * 6); });
        count.textContent = `resamples: ${upto}`;
      });
    } },
    { cap: "The <b>95% interval</b> is the middle 95% of those slopes (2.5th to 97.5th percentile). Every number in the findings carries one; a slope whose interval crosses zero isn't sure of its direction.", hold: 2600, play: async (h) => { await h.tween(500, (t) => ci.setAttribute("opacity", t)); } },
  ];
};

// ---------------------------------------------------------------- 5. Shuffle test
D.shuffle = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 380");
  const pts = saltData(31, 30, 3);
  const F = frame(svg, { x0: 80, y0: 24, w: 360, h: 260, xd: [0.4, 3.0], yd: [0, 1], xl: "chloride (log)", yl: "sensitive share",
    xt: [[0.5, "3"], [1.5, "30"], [2.5, "300"]], yt: [[0, "0"], [1, "1"]] });
  const r = rng(77);
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const dots = pts.map((p) => el("circle", { cx: F.X(p.x), cy: F.Y(p.y), r: 3.5, class: "pt" }, svg));
  const real = fit(xs, ys);
  const ln = el("line", { class: "fit" }, svg);
  const setLine = (f) => { ln.setAttribute("x1", F.X(0.6)); ln.setAttribute("y1", F.Y(f.a + f.b * 0.6)); ln.setAttribute("x2", F.X(2.8)); ln.setAttribute("y2", F.Y(f.a + f.b * 2.8)); };
  setLine(real);
  const N = 60, null_ = [];
  const shuffles = [];
  for (let k = 0; k < N; k++) { const s = [...xs]; for (let i = s.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [s[i], s[j]] = [s[j], s[i]]; } shuffles.push(s); null_.push(fit(s, ys).b); }
  const hx0 = 480, hw = 210, hy = 284;
  const lo = Math.min(real.b, ...null_) * 1.1, hi = Math.max(...null_.map(Math.abs)) * 1.3;
  const X = (v) => hx0 + ((v - lo) / (hi - lo)) * hw;
  el("line", { x1: hx0, x2: hx0 + hw, y1: hy, y2: hy, class: "ax" }, svg);
  el("text", { x: hx0 + hw / 2, y: hy + 36, class: "axl", "text-anchor": "middle", text: "slope" }, svg);
  el("line", { x1: X(0), x2: X(0), y1: hy - 4, y2: hy + 4, class: "ax" }, svg);
  el("text", { x: X(0), y: hy + 18, class: "tick", "text-anchor": "middle", text: "0" }, svg);
  const marks = null_.map(() => el("circle", { r: 4, class: "pt2", opacity: 0 }, svg));
  const stack = {};
  null_.forEach((v, k) => { const b = Math.round(X(v) / 9); stack[b] = (stack[b] || 0) + 1; marks[k].setAttribute("cx", b * 9); marks[k].setAttribute("cy", hy - 6 - (stack[b] - 1) * 9); });
  const realMark = el("g", { opacity: 0 }, svg);
  el("line", { x1: X(real.b), x2: X(real.b), y1: hy - 120, y2: hy, class: "fit", "stroke-width": 3 }, realMark);
  el("text", { x: X(real.b), y: hy - 128, class: "lbl hi", "text-anchor": "middle", text: "real" }, realMark);
  return [
    { cap: "The real slope. Could a slope this steep turn up by chance, from data with no link at all?", play: async () => {} },
    { cap: "<b>Shuffle</b>: hand the chloride readings back out at random, breaking any real link but keeping every value. Fit again.", play: async (h) => {
      for (let k = 0; k < 8; k++) {
        const s = shuffles[k];
        await h.tween(260, (t) => dots.forEach((d, i) => d.setAttribute("cx", lerp(F.X(k ? shuffles[k - 1][i] : xs[i]), F.X(s[i]), t))));
        setLine(fit(s, ys)); marks[k].setAttribute("opacity", 1); await h.wait(120);
      }
    } },
    { cap: "Many shuffles give the slopes that chance alone produces: they pile up around zero.", play: async (h) => {
      await h.tween(1000, (t) => { const upto = Math.round(lerp(8, N, t)); for (let k = 0; k < upto; k++) marks[k].setAttribute("opacity", 1); });
    } },
    { cap: "The real slope sits <b>far outside the shuffled pile</b>, so chance is a poor explanation. The engine shuffles <i>within</i> sites and seasons too, so the shuffles keep the data's structure; a real slope must beat 95% of them to pass.", hold: 2600, play: async (h) => {
      await h.tween(700, (t) => dots.forEach((d, i) => d.setAttribute("cx", lerp(F.X(shuffles[7][i]), F.X(xs[i]), t))));
      setLine(real);
      await h.tween(400, (t) => realMark.setAttribute("opacity", t));
    } },
  ];
};
})();
