/* Chart library for the findings site. Each <div class="chart" data-chart="N"> is drawn from
   the Nth spec in <script id="chart-specs" type="application/json">. Specs come from Python
   (iwla_river/web/findings); every word and number in them is computed from the data.

   Types: time, bars, stack, hbars, strip, heat, dotrank. */
(function () {
  "use strict";
  const node = document.getElementById("chart-specs");
  if (!node) return;
  const SPECS = JSON.parse(node.textContent);
  const W = 760;
  const COLORS = { accent: "var(--accent)", grey: "var(--grey)", good: "var(--good)", bad: "var(--bad)",
    warn: "var(--warn)", c1: "var(--c1)", c2: "var(--c2)", c3: "var(--c3)", c4: "var(--c4)" };
  const col = c => COLORS[c] || "var(--accent)";
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const t = d => Date.parse(d);
  const FMT = {
    int: v => String(v), comma: v => Number(v).toLocaleString("en-US"),
    pct: v => `${Math.round(v * 100)}%`, signed: v => `${v > 0 ? "+" : ""}${v}`,
    signedpct: v => `${v > 0 ? "+" : ""}${Math.round(v * 100)}`,
  };
  const yfmt = y => FMT[(y && y.fmt) || "int"];
  const tip = s => s ? `<title>${esc(s)}</title>` : "";

  function wrap(str, max) {
    const words = String(str).split(" "), lines = [];
    let cur = "";
    words.forEach(w => { if ((cur + " " + w).trim().length > max) { lines.push(cur.trim()); cur = w; } else cur += " " + w; });
    if (cur.trim()) lines.push(cur.trim());
    return lines;
  }

  // Title, subtitle and legend; returns the svg so far and the y where the plot may start.
  function header(spec) {
    let s = "", y = 0;
    wrap(spec.title || "", 86).forEach(line => { y += 20; s += `<text class="t-title" x="0" y="${y - 2}">${esc(line)}</text>`; });
    if (spec.subtitle) { y += 20; s += `<text class="t-sub" x="0" y="${y - 2}">${esc(spec.subtitle)}</text>`; }
    if (spec.legend && spec.legend.length) {
      y += 22; let x = 0;
      spec.legend.forEach(l => {
        const c = col(l.color), o = l.opacity ?? 1;
        s += l.shape === "square" ? `<rect x="${x}" y="${y - 11}" width="12" height="12" fill="${c}" fill-opacity="${o}"/>`
          : l.shape === "line" ? `<line x1="${x}" x2="${x + 16}" y1="${y - 5}" y2="${y - 5}" stroke="${c}" stroke-width="2.5" ${l.dash ? 'stroke-dasharray="5 4"' : ""}/>`
          : `<circle cx="${x + 6}" cy="${y - 5}" r="5" fill="${c}" fill-opacity="${o}"/>`;
        s += `<text class="t-label" x="${x + (l.shape === "line" ? 22 : 16)}" y="${y - 1}">${esc(l.name)}</text>`;
        x += (l.shape === "line" ? 30 : 24) + 7 * String(l.name).length + 16;
      });
    }
    return { s, top: y + 22 };
  }

  function svg(spec, h, body) {
    return `<svg viewBox="0 0 ${W} ${h}" role="img" aria-label="${esc(spec.title)}">${body}</svg>`;
  }

  // ---------- time: dots and lines over dates ----------
  function time(spec) {
    const hd = header(spec), L = 56, R = 24, B = spec.notes && spec.notes.length ? 52 : 36;
    const H = spec.height || 330, T = hd.top + 6, y = spec.y, f = yfmt(y);
    const pts = spec.series.flatMap(s => s.points);
    const xFrom = spec.x && spec.x.from || pts.reduce((a, p) => p.x < a ? p.x : a, pts[0].x);
    const xTo = spec.x && spec.x.to || pts.reduce((a, p) => p.x > a ? p.x : a, pts[0].x);
    const x0 = t(xFrom), x1 = t(xTo);
    const X = d => L + (t(d) - x0) / (x1 - x0 || 1) * (W - L - R);
    const Y = v => T + (1 - (Math.max(y.min, Math.min(y.max, v)) - y.min) / (y.max - y.min)) * (H - T - B);
    let s = hd.s;
    if (spec.band) s += `<rect x="${L}" y="${Y(spec.band.hi)}" width="${W - L - R}" height="${Y(spec.band.lo) - Y(spec.band.hi)}" fill="var(--grey)" fill-opacity=".16"/>`;
    y.ticks.forEach(v => s += `<line class="${v === 0 && y.min < 0 ? "axis" : "grid"}" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/><text class="t-axis" x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${f(v)}</text>`);
    if (y.unit) s += `<text class="t-axis" x="${L - 8}" y="${T - 10}" text-anchor="end">${esc(y.unit)}</text>`;
    // x ticks: every 5 years, every year, or January/July, by span
    const span = (x1 - x0) / 3.156e10;
    const y0 = new Date(x0).getUTCFullYear(), y1 = new Date(x1).getUTCFullYear();
    if (span > 6) for (let yy = Math.ceil(y0 / 5) * 5; yy <= y1; yy += 5) s += `<text class="t-axis" x="${X(`${yy}-01-01`)}" y="${H - B + 22}" text-anchor="middle">${yy}</text>`;
    else if (span > 2.5) for (let yy = y0 + 1; yy <= y1; yy++) s += `<text class="t-axis" x="${X(`${yy}-01-01`)}" y="${H - B + 22}" text-anchor="middle">${yy}</text>`;
    else for (let yy = y0; yy <= y1; yy++) ["01", "07"].forEach(m => { const d = `${yy}-${m}-01`; if (t(d) >= x0 && t(d) <= x1) s += `<text class="t-axis" x="${X(d)}" y="${H - B + 22}" text-anchor="middle">${m === "01" ? "Jan" : "Jul"} ${yy}</text>`; });
    (spec.refs || []).forEach(r => {
      const xa = X(r.x0 || xFrom), xb = X(r.x1 || xTo);
      s += `<line class="ref" x1="${xa}" x2="${xb}" y1="${Y(r.y)}" y2="${Y(r.y)}"/>`;
      if (r.label) s += `<text class="t-note" x="${r.labelAt === "left" ? xa + 4 : xb}" y="${Y(r.y) - 6}" text-anchor="${r.labelAt === "left" ? "start" : "end"}">${esc(r.label)}</text>`;
    });
    (spec.yNotes || []).forEach(n => s += `<text class="t-note" x="${L + 6}" y="${Y(n.y) + (n.below ? -6 : 14)}">${esc(n.text)}</text>`);
    spec.series.forEach(se => {
      const c = col(se.color), o = se.opacity ?? 0.85;
      if (se.line) s += `<polyline fill="none" stroke="${c}" stroke-width="${se.lineWidth || 1.5}" stroke-linejoin="round" points="${se.points.map(p => `${X(p.x)},${Y(p.y)}`).join(" ")}"/>`;
      if (se.dots !== false) se.points.forEach(p => s += `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="${se.r || 5}" fill="${c}" fill-opacity="${o}">${tip(p.tip)}</circle>`);
    });
    (spec.notes || []).forEach((n, i) => s += `<text class="t-note" x="${n.at === "right" ? W - R : L}" y="${H - 6 - i * 14}" text-anchor="${n.at === "right" ? "end" : "start"}">${esc(n.text)}</text>`);
    return svg(spec, H, s);
  }

  // ---------- bars: vertical bars per category ----------
  function bars(spec) {
    const hd = header(spec), L = 56, R = 16, B = 56, H = spec.height || 300, T = hd.top + 22, y = spec.y, f = yfmt(y);
    const n = spec.cats.length, band = (W - L - R) / n, bw = band * 0.62;
    const Y = v => T + (1 - (v - y.min) / (y.max - y.min)) * (H - T - B);
    let s = hd.s;
    y.ticks.forEach(v => s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/><text class="t-axis" x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${f(v)}</text>`);
    spec.cats.forEach((c, i) => {
      const x = L + i * band + (band - bw) / 2;
      s += `<rect x="${x}" y="${Y(c.value)}" width="${bw}" height="${Y(y.min) - Y(c.value)}" fill="${col(c.color || "grey")}" fill-opacity="${c.opacity ?? 0.6}">${tip(c.tip)}</rect>`;
      if (c.valueLabel) s += `<text class="t-label" x="${x + bw / 2}" y="${Y(c.value) - 6}" text-anchor="middle">${esc(c.valueLabel)}</text>`;
      if (c.note) s += `<text class="t-label" x="${x + bw / 2}" y="${Y(c.value) - 22}" text-anchor="middle" font-weight="600" fill="${col(c.color)}">${esc(c.note)}</text>`;
      s += `<text class="t-axis" x="${x + bw / 2}" y="${H - B + 18}" text-anchor="middle">${esc(c.label)}</text>`;
      if (c.sub) s += `<text class="t-note" x="${x + bw / 2}" y="${H - B + 34}" text-anchor="middle">${esc(c.sub)}</text>`;
    });
    if (spec.xLabel) s += `<text class="t-axis" x="${L + (W - L - R) / 2}" y="${H - 4}" text-anchor="middle">${esc(spec.xLabel)}</text>`;
    return svg(spec, H, s);
  }

  // ---------- stack: stacked bars (surveys, years) ----------
  function stack(spec) {
    const hd = header(spec), L = 56, R = 16, B = 30, H = spec.height || 260, T = hd.top + 4, y = spec.y, f = yfmt(y);
    const n = spec.bars.length, band = (W - L - R) / Math.max(n, 1), bw = Math.min(band * 0.72, spec.maxBar || 999);
    const Y = v => T + (1 - v / y.max) * (H - T - B);
    let s = hd.s;
    y.ticks.forEach(v => s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/><text class="t-axis" x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${f(v)}</text>`);
    spec.bars.forEach((b, i) => {
      const x = L + i * band + (band - bw) / 2; let acc = 0;
      b.segs.forEach(sg => { if (!sg.v) return; s += `<rect x="${x}" y="${Y(acc + sg.v)}" width="${bw}" height="${Y(acc) - Y(acc + sg.v)}" fill="${col(sg.color)}" fill-opacity="${sg.opacity ?? 1}">${tip(sg.tip)}</rect>`; acc += sg.v; });
      if (b.label) s += `<text class="t-axis" x="${x + bw / 2}" y="${H - B + 18}" text-anchor="middle">${esc(b.label)}</text>`;
    });
    return svg(spec, H, s);
  }

  // ---------- hbars: ranked horizontal bars ----------
  function hbars(spec) {
    const hd = header(spec), L = 290, R = 64, rowH = 26, T = hd.top, H = T + spec.rows.length * rowH + 8;
    const mx = spec.max || Math.max(...spec.rows.map(r => r.value)), X = v => L + Math.max(0, v) / mx * (W - L - R);
    let s = hd.s;
    spec.rows.forEach((r, i) => {
      const y = T + i * rowH;
      s += `<text class="t-label" x="0" y="${y + 15}">${esc(r.label)}</text><rect x="${L}" y="${y + 4}" width="${X(r.value) - L}" height="15" fill="${col(r.color || "grey")}" fill-opacity="${r.opacity ?? 0.6}"/><text class="t-note num" x="${X(r.value) + 6}" y="${y + 15}">${esc(r.valueLabel ?? r.value)}</text>`;
    });
    return svg(spec, H, s);
  }

  // ---------- strip: values per group with the mean marked ----------
  function strip(spec) {
    const hd = header(spec), L = 130, R = 24, T = hd.top + 4, rowH = 56, H = T + spec.groups.length * rowH + 30, x = spec.x;
    const X = v => L + (v - x.min) / (x.max - x.min) * (W - L - R);
    let s = hd.s;
    x.ticks.forEach(v => s += `<line class="grid" x1="${X(v)}" x2="${X(v)}" y1="${T - 6}" y2="${H - 30}"/><text class="t-axis" x="${X(v)}" y="${H - 12}" text-anchor="middle">${v}</text>`);
    spec.groups.forEach((g, i) => {
      const cy = T + i * rowH + rowH / 2;
      s += `<text class="t-label" x="0" y="${cy}">${esc(g.label)}</text><text class="t-note" x="0" y="${cy + 15}">${esc(g.sub || "")}</text>`;
      g.values.forEach((v, j) => s += `<circle cx="${X(v.v)}" cy="${cy + ((j % 5) - 2) * 4}" r="4.5" fill="var(--grey)" fill-opacity=".7">${tip(v.tip)}</circle>`);
      if (g.mean != null) s += `<line x1="${X(g.mean)}" x2="${X(g.mean)}" y1="${cy - 16}" y2="${cy + 16}" stroke="var(--accent)" stroke-width="3"/><text class="t-label" x="${X(g.mean) + 8}" y="${cy - 10}" fill="var(--accent)">${esc(g.meanLabel ?? g.mean)}</text>`;
    });
    return svg(spec, H, s);
  }

  // ---------- heat: rows by columns, cell shade = share ----------
  function heat(spec) {
    const hd = header(spec), L = 250, R = 16, rowH = 22, T = hd.top + 14, cw = (W - L - R) / spec.cols.length;
    const H = T + spec.blocks.reduce((a, b) => a + 28 + b.rows.length * rowH, 0) + 28;
    let s = hd.s;
    spec.cols.forEach((c, i) => s += `<text class="t-label" x="${L + i * cw + cw / 2}" y="${T - 8}" text-anchor="middle" font-weight="600">${esc(c)}</text>`);
    let y = T;
    spec.blocks.forEach(b => {
      y += 22; s += `<text class="t-sub" x="0" y="${y}" font-weight="600">${esc(b.name)}</text>`; y += 6;
      b.rows.forEach(r => {
        s += `<text class="t-label" x="12" y="${y + rowH / 2 + 4}">${esc(r.label)}</text>`;
        r.cells.forEach((c, i) => {
          s += `<rect x="${L + i * cw + 2}" y="${y + 1}" width="${cw - 4}" height="${rowH - 2}" rx="3" fill="var(--accent)" fill-opacity="${Math.max(c.v, 0.04).toFixed(2)}">${tip(c.tip)}</rect>`;
          s += `<text x="${L + i * cw + cw / 2}" y="${y + rowH / 2 + 4}" text-anchor="middle" font-size="11.5" class="num" fill="${c.v > 0.55 ? "var(--bg)" : "var(--ink)"}">${esc(c.text)}</text>`;
        });
        y += rowH;
      });
    });
    (spec.colNotes || []).forEach((n, i) => s += `<text class="t-note" x="${L + i * cw + cw / 2}" y="${y + 18}" text-anchor="middle">${esc(n)}</text>`);
    return svg(spec, H, s);
  }

  // ---------- dotrank: one row per item, dot on a value axis ----------
  function dotrank(spec) {
    const hd = header(spec), L = 290, R = 60, rowH = 19, T = hd.top + 8, n = spec.rows.length, x = spec.x;
    const H = T + n * rowH + 44, X = v => L + (v - x.min) / (x.max - x.min) * (W - L - R);
    let s = hd.s;
    x.ticks.forEach(v => s += `<line class="${v === 0 ? "axis" : "grid"}" x1="${X(v)}" x2="${X(v)}" y1="${T - 6}" y2="${T + n * rowH}"/><text class="t-axis" x="${X(v)}" y="${T + n * rowH + 16}" text-anchor="middle">${v > 0 ? "+" : ""}${v}</text>`);
    if (x.label) s += `<text class="t-axis" x="${X((x.min + x.max) / 2)}" y="${T + n * rowH + 34}" text-anchor="middle">${esc(x.label)}</text>`;
    spec.rows.forEach((r, i) => {
      const cy = T + i * rowH + rowH / 2;
      s += `<text class="t-label" x="0" y="${cy + 4}">${esc(r.label)}</text><text class="t-note" x="${L - 12}" y="${cy + 4}" text-anchor="end">${esc(r.note || "")}</text><circle cx="${X(r.x)}" cy="${cy}" r="5" fill="${col(r.color)}">${tip(r.tip)}</circle>`;
    });
    return svg(spec, H, s);
  }

  const DRAW = { time, bars, stack, hbars, strip, heat, dotrank };
  document.querySelectorAll(".chart[data-chart]").forEach(el => {
    const spec = SPECS[Number(el.dataset.chart)];
    try { el.innerHTML = DRAW[spec.type](spec); }
    catch (e) { el.innerHTML = `<p class="meta">This chart could not be drawn (${esc(e.message)}).</p>`; console.error(e); }
  });
})();
