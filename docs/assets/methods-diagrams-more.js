/* More method diagrams: binned averages, trends, change points, agreement, reliability, grouped cross-validation,
   clustering and the need score. Where a diagram shows real numbers it says so; dots are otherwise illustrative. */
"use strict";
(() => {
const { el, rng, lerp, fit, pct, median, frame } = window.SOS;
const D = (window.SOS_DIAGRAMS = window.SOS_DIAGRAMS || {});

// ---------------------------------------------------------------- binned averages (real numbers: paving finding)
D.bins = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 360");
  const bins = [["0–2%", 3021, 0.399], ["2–5%", 858, 0.371], ["5–10%", 749, 0.367], ["10–15%", 401, 0.330], ["15–25%", 1046, 0.264], ["25%+", 1251, 0.219]];
  const F = frame(svg, { x0: 80, y0: 20, w: 600, h: 260, xd: [0, 6], yd: [0, 0.5], xl: "share of the watershed paved", yl: "average sensitive share",
    yt: [[0, "0"], [0.1, "10%"], [0.2, "20%"], [0.3, "30%"], [0.4, "40%"], [0.5, "50%"]] });
  const r = rng(3);
  const cloud = el("g", {}, svg);
  bins.forEach((b, k) => {
    el("text", { x: F.X(k + 0.5), y: F.y0 + F.h + 19, class: "tick", "text-anchor": "middle", text: b[0] }, svg);
    for (let i = 0; i < 26; i++) el("circle", { cx: F.X(k + 0.2 + 0.6 * r()), cy: F.Y(Math.max(0.01, Math.min(0.5, b[2] + r.norm() * 0.12))), r: 2.6, class: "pt", "fill-opacity": 0.3 }, cloud);
  });
  const bars = bins.map((b, k) => el("rect", { x: F.X(k + 0.18), width: F.X(0.64) - F.X(0), y: F.Y(0), height: 0, class: "bar", "fill-opacity": 0.85 }, svg));
  const labs = bins.map((b, k) => el("text", { x: F.X(k + 0.5), y: F.Y(b[2]) - 8, class: "lbl b", "text-anchor": "middle", opacity: 0, text: `${Math.round(b[2] * 100)}%` }, svg));
  const ns = bins.map((b, k) => el("text", { x: F.X(k + 0.5), y: F.y0 + F.h + 34, class: "tick", "text-anchor": "middle", opacity: 0, text: `${b[1].toLocaleString()} surveys` }, svg));
  F.g.querySelector(".axl").setAttribute("y", F.y0 + F.h + 58);
  return [
    { cap: "Every survey (a dot; a sample shown) sorted into a bin by how much of its watershed is paved, from EPA's StreamCat map.", play: async () => {} },
    { cap: "Average the share of sensitive animals in each bin. <b>Real numbers:</b> 40% in near-natural watersheds down to 22% where a quarter or more is paved (7,326 surveys).", play: async (h) => {
      await h.tween(1100, (t) => bars.forEach((b, k) => { const v = bins[k][2] * t; b.setAttribute("y", F.Y(v)); b.setAttribute("height", F.Y(0) - F.Y(v)); }));
      labs.forEach((l) => l.setAttribute("opacity", 1)); ns.forEach((n) => n.setAttribute("opacity", 1));
      cloud.setAttribute("opacity", 0.5);
    } },
    { cap: "This is <b>description</b>, not a test: no interval, nothing held equal. It shows the shape (losses start early, well before 25% paved). Whether paving or salt does it needs the models below.", hold: 2400, play: async () => {} },
  ];
};

// ---------------------------------------------------------------- trend at a site, then across sites
D.trend = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 430");
  const r = rng(8);
  const years = 8, qcol = ["var(--c1)", "var(--c3)", "var(--c2)", "var(--c4)"];
  const pts = [];
  for (let y = 0; y < years; y++) for (let q = 0; q < 4; q++) pts.push({ t: y + q / 4 + 0.12, q, y, v: 1.55 + [0.25, 0.05, -0.12, 0.0][q] + 0.028 * y + r.norm() * 0.07 });
  const F = frame(svg, { x0: 80, y0: 20, w: 600, h: 200, xd: [0, years], yd: [1.1, 2.2], xl: "year", yl: "chloride (log)",
    xt: [0, 2, 4, 6, 8].map((v) => [v, `${2017 + v}`]), yt: [[1.3, "20"], [1.7, "50"], [2.0, "100"]] });
  const dots = pts.map((p) => el("circle", { cx: F.X(p.t), cy: F.Y(p.v), r: 5, class: "pt" }, svg));
  const key = el("g", { opacity: 0 }, svg);
  ["winter", "spring", "summer", "fall"].forEach((s, q) => { el("circle", { cx: 500 + q * 52, cy: 30, r: 5, style: `fill:${qcol[q]}` }, key); el("text", { x: 508 + q * 52, y: 35, class: "tick", text: s }, key); });
  // seasonal Kendall: compare each pair of years within a season
  const pairs = [];
  for (let q = 0; q < 4; q++) { const s = pts.filter((p) => p.q === q); for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++) pairs.push([s[i], s[j]]); }
  const up = pairs.filter(([a, b]) => b.v > a.v).length, down = pairs.length - up;
  const slopes = pairs.map(([a, b]) => (b.v - a.v) / (b.t - a.t));
  const sen = median(slopes);
  const demo = el("g", {}, svg);
  const counter = el("text", { x: 90, y: 284, class: "lbl", text: "" }, svg);
  const mid = pts.reduce((s, p) => s + p.v, 0) / pts.length;
  const senLine = el("line", { x1: F.X(0), y1: F.Y(mid - sen * 4), x2: F.X(8), y2: F.Y(mid + sen * 4), class: "fit", opacity: 0 }, svg);
  // 396 sites
  const gx = 90, gy = 280, cell = 11, cols = 50;
  const tiles = [];
  const order = Array.from({ length: 396 }, (_, i) => i).sort(() => r() - 0.5);
  for (let i = 0; i < 396; i++) tiles.push(el("rect", { x: gx + (i % cols) * cell, y: gy + Math.floor(i / cols) * cell, width: cell - 2, height: cell - 2, rx: 2, class: "bar m", opacity: 0 }, svg));
  const res = el("text", { x: gx, y: gy + 8 * cell + 24, class: "lbl b", opacity: 0, text: "69 rising   ·   12 falling   ·   315 no clear trend" }, svg);
  return [
    { cap: "Chloride at one site, read each season for eight years (illustrative). Winter readings sit high because of road salt, so a plain line through all of them would mix season with trend.", play: async (h) => {
      await h.tween(600, (t) => { key.setAttribute("opacity", t); dots.forEach((d, i) => d.setAttribute("style", `fill:${qcol[pts[i].q]}`)); });
    } },
    { cap: "<b>Seasonal Kendall test:</b> compare only like with like: every winter with every later winter, every summer with every later summer. Count how often the later reading is higher.", play: async (h) => {
      const show = pairs.filter(([a]) => a.q === 0).slice(0, 14);
      for (const [a, b] of show) {
        const ln = el("line", { x1: F.X(a.t), y1: F.Y(a.v), x2: F.X(b.t), y2: F.Y(b.v), class: b.v > a.v ? "fit" : "fit acc", "stroke-width": 1.4, opacity: 0.6 }, demo);
        await h.wait(110); void ln;
      }
      counter.textContent = `later higher: ${up}   later lower: ${down}   (out of ${pairs.length} same-season pairs)`;
    } },
    { cap: `Far more ups than downs is a trend; the test gives its p-value. <b>Sen's slope</b> is the median of all those pairwise slopes: here ${(100 * (10 ** sen - 1)).toFixed(1)}% a year. Medians shrug off a single storm reading.`, play: async (h) => {
      await h.tween(500, (t) => demo.setAttribute("opacity", 1 - t));
      await h.tween(700, (t) => senLine.setAttribute("opacity", t));
    } },
    { cap: "Repeat at every site with at least 8 readings over 4+ years: <b>396 sites</b>. Testing that many, some would look like trends by luck, so the p-values are adjusted for <b>false discovery rate</b> (Benjamini–Hochberg, 5%).", play: async (h) => {
      await h.tween(700, (t) => tiles.forEach((tl) => tl.setAttribute("opacity", t)));
    } },
    { cap: "<b>Real result:</b> 69 sites rising and 12 falling (median +6.3% a year at rising sites). The network-wide trend is not clear, because short-lived Salt Watch sites come and go; the per-site count is the better measure.", hold: 2600, play: async (h) => {
      await h.tween(1200, (t) => { const k = Math.round(t * 81); for (let i = 0; i < k; i++) tiles[order[i]].setAttribute("class", i < 69 ? "bar hi" : "bar"); });
      res.setAttribute("opacity", 1);
    } },
  ];
};

// ---------------------------------------------------------------- change point (nCPA)
D.changepoint = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 450");
  const r = rng(14); const pts = [];
  for (let i = 0; i < 140; i++) { const x = 0.6 + r() * 2.2; const cl = 10 ** x; pts.push({ x, y: (cl < 47 ? 8.6 : 6.9) + r.norm() * 1.4 }); }
  const F = frame(svg, { x0: 80, y0: 20, w: 600, h: 220, xd: [0.5, 2.9], yd: [2, 13], xl: "chloride, mg/L (log scale)", yl: "bug score (of 12)",
    xt: [[1, "10"], [Math.log10(47), "47"], [2, "100"], [Math.log10(230), "230"], [2.7, "500"]], yt: [[4, "4"], [8, "8"], [12, "12"]] });
  pts.forEach((p) => el("circle", { cx: F.X(p.x), cy: F.Y(p.y), r: 3.5, class: "pt", "fill-opacity": 0.45 }, svg));
  const xs = [...new Set(pts.map((p) => p.x))].sort((a, b) => a - b);
  const total = (() => { const m = pts.reduce((s, p) => s + p.y, 0) / pts.length; return pts.reduce((s, p) => s + (p.y - m) ** 2, 0); })();
  const cands = [];
  for (let i = 5; i < xs.length - 5; i += 1) {
    const c = (xs[i] + xs[i + 1]) / 2; const L = pts.filter((p) => p.x < c), R = pts.filter((p) => p.x >= c);
    const ml = L.reduce((s, p) => s + p.y, 0) / L.length, mr = R.reduce((s, p) => s + p.y, 0) / R.length;
    const dev = L.reduce((s, p) => s + (p.y - ml) ** 2, 0) + R.reduce((s, p) => s + (p.y - mr) ** 2, 0);
    cands.push({ c, ml, mr, gain: 1 - dev / total });
  }
  const best = cands.reduce((a, b) => (b.gain > a.gain ? b : a));
  // the gain curve below
  const gy0 = 300, gh = 90, gmax = Math.max(...cands.map((c) => c.gain));
  el("line", { x1: F.x0, x2: F.x0 + F.w, y1: gy0 + gh, y2: gy0 + gh, class: "ax" }, svg);
  el("text", { x: 18, y: gy0 + gh / 2, class: "axl", "text-anchor": "middle", transform: `rotate(-90 18 ${gy0 + gh / 2})`, text: "spread explained" }, svg);
  const curve = el("path", { class: "fit acc", "stroke-width": 2, d: "" }, svg);
  const split = el("line", { y1: F.y0, y2: gy0 + gh, class: "guide", opacity: 0 }, svg);
  const segL = el("line", { class: "fit", "stroke-width": 3, opacity: 0 }, svg), segR = el("line", { class: "fit", "stroke-width": 3, opacity: 0 }, svg);
  const at = (c) => { split.setAttribute("x1", F.X(c.c)); split.setAttribute("x2", F.X(c.c));
    segL.setAttribute("x1", F.X(0.5)); segL.setAttribute("x2", F.X(c.c)); segL.setAttribute("y1", F.Y(c.ml)); segL.setAttribute("y2", F.Y(c.ml));
    segR.setAttribute("x1", F.X(c.c)); segR.setAttribute("x2", F.X(2.9)); segR.setAttribute("y1", F.Y(c.mr)); segR.setAttribute("y2", F.Y(c.mr)); };
  const band = el("rect", { x: F.X(Math.log10(25)), width: F.X(Math.log10(54)) - F.X(Math.log10(25)), y: F.y0, height: F.h, class: "band", opacity: 0 }, svg);
  const epa = el("g", { opacity: 0 }, svg);
  el("line", { x1: F.X(Math.log10(230)), x2: F.X(Math.log10(230)), y1: F.y0, y2: F.y0 + F.h, class: "guide" }, epa);
  el("text", { x: F.X(Math.log10(230)) + 6, y: F.y0 + 14, class: "lbl m", text: "EPA chronic limit 230" }, epa);
  const bestLbl = el("text", { x: F.X(Math.log10(47)), y: F.y0 + 14, class: "lbl hi", "text-anchor": "middle", opacity: 0, text: "47 mg/L (90%: 25–54)" }, svg);
  return [
    { cap: "Volunteer rocky-bottom surveys against chloride within 30 days (illustrative dots with the real form's shape). Is there a level where scores step down?", play: async () => {} },
    { cap: "<b>Change-point search (nCPA):</b> try every split between two neighbouring chloride values. For each, average the scores on each side and ask how much of the spread the two averages explain.", play: async (h) => {
      split.setAttribute("opacity", 1); segL.setAttribute("opacity", 1); segR.setAttribute("opacity", 1);
      await h.tween(2600, (t) => {
        const k = Math.max(1, Math.round(t * (cands.length - 1)));
        at(cands[k]);
        curve.setAttribute("d", cands.slice(0, k + 1).map((c, i) => `${i ? "L" : "M"}${F.X(c.c).toFixed(1)} ${(gy0 + gh - (c.gain / gmax) * gh).toFixed(1)}`).join(""));
      });
    } },
    { cap: "The split that explains the most is the <b>change point</b>. Splits only fall between distinct readings, never inside a run of identical ones.", play: async (h) => {
      at(best); await h.tween(400, (t) => bestLbl.setAttribute("opacity", t));
    } },
    { cap: "<b>How sure?</b> Redo the search on 500 resamples of whole sites; the middle 90% of the change points is the interval. <b>Real:</b> rocky-bottom form 47 mg/L (25–54), original SOS form 60 (48–165): each form gets its own, because they score on different scales.", play: async (h) => {
      await h.tween(600, (t) => band.setAttribute("opacity", t));
    } },
    { cap: "Both sit far below EPA's chronic limit of 230 mg/L: the animals respond to salt well before the legal line.", hold: 2600, play: async (h) => { await h.tween(500, (t) => epa.setAttribute("opacity", t)); } },
  ];
};

// ---------------------------------------------------------------- agreement: a reading against a reference, and classes
D.agreement = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 400");
  const r = rng(19); const pts = [];
  for (let i = 0; i < 120; i++) { const a = 0.9 + r() * 1.9; pts.push({ a, v: a + r.norm() * 0.2 }); }
  const F = frame(svg, { x0: 70, y0: 20, w: 300, h: 300, xd: [0.7, 3.0], yd: [0.7, 3.0], xl: "agency lab chloride (log)", yl: "volunteer kit (log)",
    xt: [[1, "10"], [2, "100"], [3, "1000"]], yt: [[1, "10"], [2, "100"], [3, "1000"]] });
  const L2 = Math.log10(2);
  const band = el("path", { d: `M${F.X(0.7)} ${F.Y(0.7 + L2)} L${F.X(3 - L2)} ${F.Y(3)} L${F.X(3)} ${F.Y(3)} L${F.X(3)} ${F.Y(3 - L2)} L${F.X(0.7 + L2)} ${F.Y(0.7)} L${F.X(0.7)} ${F.Y(0.7)} Z`, class: "band", opacity: 0 }, svg);
  const one = el("line", { x1: F.X(0.7), y1: F.Y(0.7), x2: F.X(3), y2: F.Y(3), class: "guide", opacity: 0 }, svg);
  const dots = pts.map((p) => el("circle", { cx: F.X(p.a), cy: F.Y(p.v), r: 3.5, class: "pt" }, svg));
  const inside = pts.filter((p) => Math.abs(p.v - p.a) <= L2).length;
  const t1 = el("text", { x: 80, y: 385, class: "lbl acc", opacity: 0, text: `${Math.round((100 * inside) / pts.length)}% within a factor of two here; real kit: 86%, r 0.70 (0.58–0.79)` }, svg);
  // classes table (illustrative counts; the real totals are in the card)
  const tx = 450, ty = 70, c = 66, cls = ["Good", "Fair", "Poor"];
  const M = [[5, 2, 0], [1, 4, 1], [0, 1, 4]];
  const tab = el("g", { opacity: 0 }, svg);
  el("text", { x: tx + 1.5 * c, y: ty - 34, class: "lbl b", "text-anchor": "middle", text: "professional rating" }, tab);
  el("text", { x: tx - 64, y: ty + 1.5 * c, class: "lbl b", "text-anchor": "middle", transform: `rotate(-90 ${tx - 64} ${ty + 1.5 * c})`, text: "volunteer rating" }, tab);
  const cells = [];
  cls.forEach((n, j) => el("text", { x: tx + j * c + c / 2, y: ty - 10, class: "tick", "text-anchor": "middle", text: n }, tab));
  cls.forEach((n, i) => {
    el("text", { x: tx - 8, y: ty + i * c + c / 2 + 4, class: "tick", "text-anchor": "end", text: n }, tab);
    cls.forEach((_, j) => {
      const rect = el("rect", { x: tx + j * c, y: ty + i * c, width: c - 3, height: c - 3, rx: 4, class: "box" }, tab);
      el("text", { x: tx + j * c + c / 2 - 1, y: ty + i * c + c / 2 + 6, class: "lbl b", "text-anchor": "middle", text: M[i][j] }, tab);
      cells.push({ i, j, rect });
    });
  });
  el("text", { x: tx, y: ty + 3 * c + 22, class: "tick", text: "illustrative counts" }, tab);
  const kap = el("text", { x: tx - 20, y: ty + 3 * c + 48, class: "lbl acc", opacity: 0 }, svg);
  el("tspan", { x: tx - 20, text: "real (within 1 km): 67% same class," }, kap);
  el("tspan", { x: tx - 20, dy: 18, text: "weighted kappa 0.50" }, kap);
  return [
    { cap: "Each dot pairs a volunteer chloride reading with an agency lab reading from the same small watershed within a week (illustrative).", play: async () => {} },
    { cap: "Perfect agreement would put every dot on the dashed line. The shaded band is <b>within a factor of two</b>; the correlation (on logs) says how well the two rise and fall together, with an interval from resampling whole watersheds.", play: async (h) => {
      await h.tween(800, (t) => { one.setAttribute("opacity", t); band.setAttribute("opacity", t); });
      await h.tween(500, (t) => { t1.setAttribute("opacity", t); dots.forEach((d, i) => { if (Math.abs(pts[i].v - pts[i].a) > L2) d.setAttribute("class", "pt2"); }); });
    } },
    { cap: "For bug surveys, volunteers and professionals each rate a stream <b>Good, Fair or Poor</b> on their own scales. Cross-tabulate the ratings where both surveyed nearby.", play: async (h) => { await h.tween(700, (t) => tab.setAttribute("opacity", t)); } },
    { cap: "The diagonal is agreement. <b>Weighted kappa</b> counts agreement beyond what chance would give, and gives half credit for a near miss (Good vs Fair) but none for Good vs Poor. Cells above the diagonal are volunteers rating a stream healthier.", hold: 2600, play: async (h) => {
      await h.tween(600, () => cells.forEach((cl) => cl.rect.setAttribute("class", cl.i === cl.j ? "boxa" : "box")));
      kap.setAttribute("opacity", 1);
    } },
  ];
};

// ---------------------------------------------------------------- reliability: ICC and how many visits
D.reliability = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 400");
  const r = rng(23);
  const sites = Array.from({ length: 8 }, (_, s) => ({ m: 0.12 + s * 0.07 + r.norm() * 0.02, v: Array.from({ length: 5 }, () => 0) }));
  sites.forEach((s) => (s.v = s.v.map(() => Math.min(0.95, Math.max(0.02, s.m + r.norm() * 0.08)))));
  const x0 = 70, w = 300, y0 = 30, hh = 260, Y = (v) => y0 + hh - (v / 0.8) * hh;
  el("line", { x1: x0, y1: y0, x2: x0, y2: y0 + hh, class: "ax" }, svg);
  el("text", { x: 18, y: y0 + hh / 2, class: "axl", "text-anchor": "middle", transform: `rotate(-90 18 ${y0 + hh / 2})`, text: "sensitive share" }, svg);
  el("text", { x: x0 + w / 2, y: y0 + hh + 24, class: "axl", "text-anchor": "middle", text: "8 sites, 5 surveys each" }, svg);
  const marks = [];
  sites.forEach((s, k) => { const cx = x0 + 20 + k * 36; s.v.forEach((v) => marks.push(el("circle", { cx: cx + (r() - 0.5) * 10, cy: Y(v), r: 4, class: "pt" }, svg))); s.line = el("line", { x1: cx - 13, x2: cx + 13, y1: Y(s.m), y2: Y(s.m), class: "fit", opacity: 0 }, svg); });
  const split = el("g", { opacity: 0 }, svg);
  el("rect", { x: x0, y: y0 + hh + 40, width: w * 0.64, height: 16, class: "bar" }, split);
  el("rect", { x: x0 + w * 0.64, y: y0 + hh + 40, width: w * 0.36, height: 16, class: "bar m" }, split);
  el("text", { x: x0, y: y0 + hh + 76, class: "lbl acc", text: "64% between sites (ICC)" }, split);
  el("text", { x: x0 + w, y: y0 + hh + 76, class: "lbl m", "text-anchor": "end", text: "36% visit to visit" }, split);
  // Spearman-Brown curve, real values
  const C = frame(svg, { x0: 450, y0: 30, w: 240, h: 260, xd: [0, 10], yd: [0.5, 1], xl: "surveys averaged", yl: "", xt: [[1, "1"], [3, "3"], [6, "6"], [10, "10"]], yt: [[0.6, "0.6"], [0.8, "0.8"], [1, "1"]] });
  const icc = 0.64, sb = (k) => (k * icc) / (1 + (k - 1) * icc);
  el("text", { x: 450, y: 22, class: "axl", text: "reliability of a site's average" }, svg);
  el("line", { x1: C.X(0), x2: C.X(10), y1: C.Y(0.8), y2: C.Y(0.8), class: "guide" }, svg);
  const curve = el("path", { class: "fit acc", d: "" }, svg);
  const pts = [[1, 0.64], [2, 0.78], [3, 0.84], [4, 0.88], [6, 0.92], [10, 0.95]].map(([k, v]) => el("circle", { cx: C.X(k), cy: C.Y(v), r: 4.5, class: "pt2", opacity: 0 }, svg));
  const three = el("text", { x: C.X(3) + 8, y: C.Y(0.84) + 18, class: "lbl hi", opacity: 0, text: "3 surveys: 0.84" }, svg);
  return [
    { cap: "Eight sites, five surveys each (illustrative). Each survey is noisy: same site, different day, different volunteer, different riffle.", play: async () => {} },
    { cap: "Each site has its own long-run level (the bars). A <b>mixed model</b> splits the total spread into <b>between sites</b> and <b>visit to visit</b>.", play: async (h) => { await h.tween(700, (t) => sites.forEach((s) => s.line.setAttribute("opacity", t))); } },
    { cap: "<b>Real:</b> 64% of the variation is the site itself (ICC 0.64, interval 0.61–0.68 from resampling sites). That is the reliability of a single survey.", play: async (h) => { await h.tween(600, (t) => split.setAttribute("opacity", t)); } },
    { cap: "Averaging k surveys cancels visit-to-visit noise. The <b>Spearman–Brown</b> formula k·r / (1 + (k−1)·r) gives the reliability of that average: <b>3 surveys reach 0.84</b>; past about 6, more visits add little.", hold: 2800, play: async (h) => {
      await h.tween(1200, (t) => { const kmax = 1 + 9 * t; let d = ""; for (let k = 1; k <= kmax; k += 0.1) d += `${d ? "L" : "M"}${C.X(k).toFixed(1)} ${C.Y(sb(k)).toFixed(1)}`; curve.setAttribute("d", d); });
      pts.forEach((p) => p.setAttribute("opacity", 1)); three.setAttribute("opacity", 1);
    } },
  ];
};

// ---------------------------------------------------------------- grouped cross-validation
D.groupcv = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 400");
  const r = rng(29); const n = 25, fold = Array.from({ length: n }, (_, i) => i % 5).sort(() => r() - 0.5);
  const pal = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--bad)"];
  const tiles = [];
  for (let i = 0; i < n; i++) {
    const x = 70 + (i % 5) * 64, y = 40 + Math.floor(i / 5) * 52;
    const g = el("g", {}, svg);
    el("rect", { x, y, width: 56, height: 42, rx: 6, class: "box" }, g);
    const vs = []; for (let k = 0; k < 3 + (i % 3); k++) vs.push(el("circle", { cx: x + 10 + k * 9, cy: y + 21 + (k % 2 ? 6 : -6), r: 3.5, class: "pt" }, g));
    tiles.push({ g, vs, rect: g.firstChild, f: fold[i] });
  }
  el("text", { x: 70, y: 26, class: "lbl b", text: "25 sites, each with its own surveys" }, svg);
  const tag = el("text", { x: 70, y: 318, class: "lbl", text: "" }, svg);
  const bars = [["all 20 map inputs", 0.46, 0.40, 0.48], ["land and pollution only", 0.43, 0.39, 0.45], ["paved share alone", 0.41, 0.39, 0.43], ["road density alone", 0.29, 0.27, 0.33]];
  const bx = 470, bw = 220, B = el("g", { opacity: 0 }, svg);
  el("text", { x: bx, y: 26, class: "lbl b", text: "R² for unseen sites (real)" }, B);
  bars.forEach(([lab, v, lo, hi], k) => {
    const y = 50 + k * 58;
    el("text", { x: bx, y, class: "tick", text: lab }, B);
    el("rect", { x: bx, y: y + 6, width: bw * v, height: 16, class: "bar" }, B);
    el("line", { x1: bx + bw * lo, x2: bx + bw * hi, y1: y + 14, y2: y + 14, class: "fit", "stroke-width": 2 }, B);
    el("text", { x: bx + bw * hi + 6, y: y + 19, class: "lbl b", text: v.toFixed(2) }, B);
  });
  return [
    { cap: "To ask how well <b>map data alone</b> predict a site's bugs, a model (LightGBM, a boosted set of decision trees) must be tested on sites it never saw.", play: async () => {} },
    { cap: "<b>Grouped cross-validation:</b> deal whole sites into 5 folds, never splitting a site's surveys between folds.", play: async (h) => {
      await h.tween(800, () => tiles.forEach((t) => t.vs.forEach((v) => v.setAttribute("style", `fill:${pal[t.f]}`))));
    } },
    { cap: "Train on four folds, predict the fifth; repeat so every site is predicted once by a model that never saw it. Then reshuffle the folds and do it all 5 times.", play: async (h) => {
      for (let f = 0; f < 5; f++) {
        tiles.forEach((t) => { t.rect.setAttribute("class", t.f === f ? "boxa" : "box"); t.g.setAttribute("opacity", t.f === f ? 1 : 0.45); });
        tag.textContent = `fold ${f + 1}: predict the highlighted sites, train on the rest`;
        await h.wait(700);
      }
      tiles.forEach((t) => { t.rect.setAttribute("class", "box"); t.g.setAttribute("opacity", 1); });
    } },
    { cap: "Why whole sites? If a site's other surveys were in training, the model would just <i>recognise the site</i> and score too well (on the IWLA data, 0.52 instead of 0.40).", play: async (h) => { tag.textContent = "a site's surveys stay together, always"; await h.wait(200); } },
    { cap: "<b>Real:</b> maps predict 46% of the differences between sites' averages; paving alone gets most of the way (0.41). The rest is local (shade, banks, culverts, springs) and only a survey finds it.", hold: 2800, play: async (h) => { await h.tween(700, (t) => B.setAttribute("opacity", t)); } },
  ];
};

// ---------------------------------------------------------------- clustering
D.clusters = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 420");
  const r = rng(41);
  const centres = [[0.15, 0.15], [0.2, 0.75], [0.8, 0.25], [0.75, 0.8], [0.5, 0.5]];
  const pts = []; centres.forEach((c, k) => { const m = [60, 12, 12, 16, 10][k]; for (let i = 0; i < m; i++) pts.push([Math.min(0.98, Math.max(0.02, c[0] + r.norm() * 0.07)), Math.min(0.98, Math.max(0.02, c[1] + r.norm() * 0.07))]); });
  const F = frame(svg, { x0: 70, y0: 20, w: 320, h: 300, xd: [0, 1], yd: [0, 1], xl: "paving (scaled)", yl: "farming pressure (scaled)" });
  const dots = pts.map((p) => el("circle", { cx: F.X(p[0]), cy: F.Y(p[1]), r: 4, class: "pt", style: "fill:var(--grey)" }, svg));
  const pal = ["var(--c3)", "var(--c4)", "var(--c2)", "var(--bad)", "var(--c1)"];
  let C = [[0.4, 0.3], [0.45, 0.6], [0.6, 0.4], [0.3, 0.45], [0.55, 0.55]];
  const cm = C.map((c, k) => el("path", { d: "", class: "fit", "stroke-width": 3, style: `stroke:${pal[k]}`, opacity: 0 }, svg));
  const cross = (k, x, y) => cm[k].setAttribute("d", `M${F.X(x) - 8} ${F.Y(y) - 8}l16 16M${F.X(x) + 8} ${F.Y(y) - 8}l-16 16`);
  const assign = () => pts.map((p) => { let b = 0, bd = 9; C.forEach((c, k) => { const d = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2; if (d < bd) { bd = d; b = k; } }); return b; });
  // silhouette by k (illustrative shape; the real peak is k = 5 at 0.427)
  const sil = [0.31, 0.33, 0.38, 0.427, 0.40, 0.36, 0.34, 0.32];
  const S = el("g", { opacity: 0 }, svg);
  const sx = 450, sw = 230, sy = 40, sh = 120;
  el("text", { x: sx, y: sy - 14, class: "lbl b", text: "how well separated, by number of types" }, S);
  sil.forEach((v, i) => { el("rect", { x: sx + i * (sw / 8) + 2, y: sy + sh - (v / 0.5) * sh, width: sw / 8 - 4, height: (v / 0.5) * sh, class: i === 3 ? "bar hi" : "bar m" }, S); el("text", { x: sx + i * (sw / 8) + sw / 16, y: sy + sh + 16, class: "tick", "text-anchor": "middle", text: i + 2 }, S); });
  el("text", { x: sx, y: sy + sh + 36, class: "tick", text: "silhouette (k = 5 is real: 0.427; others sketched)" }, S);
  const T = el("g", { opacity: 0 }, svg);
  const types = [["low-pressure", 40, 0.97], ["livestock", 42, 0.99], ["mining", 35, 0.81], ["cropland", 33, 0.99], ["urban", 27, 0.91]];
  el("text", { x: sx, y: 232, class: "lbl b", text: "median sensitive share by type (real)" }, T);
  types.forEach(([n, v, j], k) => { const y = 250 + k * 30; el("text", { x: sx, y: y + 13, class: "tick", text: n }, T); el("rect", { x: sx + 92, y, width: v * 1.6, height: 16, class: n === "urban" ? "bar hi" : "bar" }, T); el("text", { x: sx + 98 + v * 1.6, y: y + 13, class: "lbl b", text: `${v}%` }, T); el("text", { x: 712, y: y + 13, class: "tick", "text-anchor": "end", text: `stable ${j}` }, T); });
  return [
    { cap: "Each dot is a small watershed with 3+ bug surveys, placed by its pressures (8 in the real analysis; 2 drawn). The bugs are <b>not</b> used to group them.", play: async () => {} },
    { cap: "<b>k-means:</b> drop 5 centres, give each watershed to its nearest centre, move each centre to the middle of its group, and repeat until nothing moves.", play: async (h) => {
      cm.forEach((c) => c.setAttribute("opacity", 1)); C.forEach((c, k) => cross(k, c[0], c[1]));
      for (let it = 0; it < 5; it++) {
        const a = assign(); dots.forEach((d, i) => d.setAttribute("style", `fill:${pal[a[i]]}`)); await h.wait(450);
        const N = C.map((c, k) => { const g = pts.filter((_, i) => a[i] === k); return g.length ? [g.reduce((s, p) => s + p[0], 0) / g.length, g.reduce((s, p) => s + p[1], 0) / g.length] : c; });
        const old = C.map((c) => [...c]);
        await h.tween(500, (t) => N.forEach((n, k) => cross(k, lerp(old[k][0], n[0], t), lerp(old[k][1], n[1], t))));
        C = N;
      }
    } },
    { cap: "How many types? Try 2 to 9 and score each by <b>silhouette</b>: how much closer each watershed is to its own type than to the next. Five types scored best.", play: async (h) => { await h.tween(600, (t) => S.setAttribute("opacity", t)); } },
    { cap: "Are the types real or an accident of this sample? Re-cluster 30 random 80% subsets: the types came back the same (mean ARI 0.94); mining was the least stable (0.81).", play: async () => {} },
    { cap: "<b>Only then</b> look at the bugs: urban watersheds hold the fewest sensitive animals (27% vs 40%); livestock watersheds score like low-pressure ones.", hold: 2800, play: async (h) => { await h.tween(700, (t) => T.setAttribute("opacity", t)); } },
  ];
};

// ---------------------------------------------------------------- need score and coverage
D.needscore = (svg) => {
  svg.setAttribute("viewBox", "0 0 720 380");
  const layers = [["impaired water", 1], ["salt impairment", 1], ["major discharge permit", 1], ["discharger out of compliance", 1], ["10%+ paved", 1], ["5+ points newly paved", 1], ["mine features", 1], ["impaired biology", 2]];
  const lx = 40, ly = 40, have = [1, 0, 1, 1, 1, 0, 0, 2];
  const rows = layers.map(([n, p], k) => {
    const g = el("g", {}, svg);
    el("rect", { x: lx, y: ly + k * 34, width: 250, height: 28, rx: 5, class: "box" }, g);
    el("text", { x: lx + 10, y: ly + k * 34 + 19, class: "lbl", text: n }, g);
    const pt = el("text", { x: lx + 240, y: ly + k * 34 + 19, class: "lbl b", "text-anchor": "end", text: `+${p}` }, g);
    return { g, rect: g.firstChild, pt, on: have[k] > 0 };
  });
  el("text", { x: lx, y: 26, class: "lbl b", text: "one watershed's pressures (public maps)" }, svg);
  const score = el("text", { x: lx, y: ly + 8 * 34 + 30, class: "lbl acc", text: "" }, svg);
  const bands = [["0–1", 91, 14615], ["2–3", 93, 5716], ["4–5", 71, 1928], ["6–9", 23, 438]];
  const bx = 400, B = el("g", { opacity: 0 }, svg);
  el("text", { x: bx, y: 26, class: "lbl b", text: "share with an active volunteer site (real)" }, B);
  bands.forEach(([n, a, t], k) => { const y = 50 + k * 50, v = a / t; el("text", { x: bx, y: y + 14, class: "tick", text: `need ${n}` }, B); el("rect", { x: bx + 64, y, width: Math.max(2, v * 2600), height: 20, class: k >= 2 ? "bar hi" : "bar" }, B); el("text", { x: bx + 70 + v * 2600, y: y + 15, class: "lbl b", text: `${(100 * v).toFixed(1)}%  (${a}/${t.toLocaleString()})` }, B); });
  const big = el("text", { x: 712, y: 290, "text-anchor": "end", class: "lbl hi", opacity: 0, text: "1,039 of 1,093 high-need watersheds have no monitor" }, svg);
  return [
    { cap: "For each of 22,697 small watersheds, public maps say which pressures are present: EPA impairments and permits, paving from land-cover maps, mine records.", play: async () => {} },
    { cap: "<b>Add them up</b> into a need score (impaired biology counts double). It is a simple count, deliberately: easy to check and to argue with.", play: async (h) => {
      let s = 0;
      for (const rw of rows) { if (rw.on) { rw.rect.setAttribute("class", "boxa"); s += +rw.pt.textContent.slice(1); score.textContent = `need score: ${s}`; } else rw.g.setAttribute("opacity", 0.45); await h.wait(220); }
    } },
    { cap: "Then <b>overlay</b> where volunteers surveyed bugs since 2021 and count, by need band. Coverage rises with need, but stays tiny.", play: async (h) => { await h.tween(700, (t) => B.setAttribute("opacity", t)); } },
    { cap: "<b>Real:</b> of 1,093 watersheds with five or more pressures, 1,039 have no active volunteer bug site; 135 of those are within 25 km of one, so they are recruitment targets.", hold: 2600, play: async (h) => { await h.tween(400, (t) => big.setAttribute("opacity", t)); } },
  ];
};
})();
