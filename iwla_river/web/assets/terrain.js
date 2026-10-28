// Terrain for the Explore map: shaded relief under the map, named peaks with heights,
// and the real source-to-mouth height profile of a river. Data from iwla_river/terrain.py.
(function () {
  "use strict";
  const BASE = "data/terrain/";
  // Same stops as terrain.RAMP (metres -> colour).
  const RAMP = [[0, "#c8e0b8"], [150, "#d6e7ba"], [400, "#e6e2b2"], [800, "#e2ce9c"], [1300, "#ceb080"],
                [2000, "#b2906c"], [3000, "#987c68"], [4000, "#c4bab2"], [5200, "#f4f4f6"]];
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = n => Math.round(n).toLocaleString("en-US");
  let INDEX = null, PEAKS = null, ready = null, last = "us";

  function keyFor(country, code) {
    code = code || "";
    if (!INDEX) return null;
    if (country === "in" || code[0] === "I") {
      const g = code.slice(0, 2);
      return code.length >= 2 && INDEX[g] ? g : INDEX.in ? "in" : null;
    }
    const h = code.slice(0, 4);
    return code.length >= 4 && INDEX[h] ? h : INDEX.us ? "us" : null;
  }

  function load(country, code) {
    if (country) last = country;
    if (!ready) ready = Promise.all([
      fetch(BASE + "index.json").then(r => r.ok ? r.json() : {}).catch(() => ({})),
      fetch(BASE + "peaks.json").then(r => r.ok ? r.json() : {}).catch(() => ({})),
    ]).then(([i, p]) => { INDEX = i; PEAKS = p; });
    return ready.then(() => keyFor(last, code));
  }

  // <image> placed by its projected bbox. X, Y map a projected [x, y] to screen.
  function layer(code, X, Y, W, H, sc) {
    const k = keyFor(last, code);
    if (!k) return "";
    const [x0, y0, x1, y1] = INDEX[k].bbox;
    const x = X([x0, y1]), y = Y([x0, y1]), w = (x1 - x0) * sc, h = (y1 - y0) * sc;
    return `<image class="ex-terrain" href="${BASE}${k}.png" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" preserveAspectRatio="none" aria-hidden="true"/>`;
  }

  // Peaks inside the view: the highest few labelled, the rest as small triangles with a tooltip.
  function peaks(code, X, Y, albers, W, H) {
    const k = keyFor(last, code);
    const list = (PEAKS && PEAKS[k]) || [];
    const boxes = [];
    let s = "", big = "", labels = 0;   // small markers first, labelled ones on top
    list.forEach(([name, lo, la, m]) => {
      const q = albers(la, lo), x = X(q), y = Y(q);
      if (x < 4 || y < 4 || x > W - 4 || y > H - 4) return;
      const text = `${name} ${fmt(m)} m`, tw = text.length * 6.1 + 4;
      const right = x + 7 + tw < W - 2;
      const bx = right ? x + 6 : x - 6 - tw, box = [bx, y - 9, bx + tw, y + 5, x, y];
      const free = labels < 8 && !boxes.some(b => (box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1]) || Math.hypot(x - b[4], y - b[5]) < 34);   // keep labelled summits apart
      const tri = (r) => `<path class="ex-peak" d="M${x.toFixed(1)} ${(y - r).toFixed(1)}L${(x + r * 0.95).toFixed(1)} ${(y + r * 0.7).toFixed(1)}L${(x - r * 0.95).toFixed(1)} ${(y + r * 0.7).toFixed(1)}Z"/>`;
      if (free) {
        boxes.push(box); labels++;
        big += `<g class="ex-peak-g"><title>${esc(text)}</title>${tri(5)}<text class="ex-peak-label" x="${(right ? x + 7 : x - 7).toFixed(1)}" y="${(y + 3.5).toFixed(1)}" text-anchor="${right ? "start" : "end"}">${esc(name)} <tspan class="ex-peak-m">${fmt(m)} m</tspan></text></g>`;
      } else {
        s += `<g class="ex-peak-g small"><title>${esc(text)}</title>${tri(3.2)}</g>`;
      }
    });
    return s || big ? `<g class="ex-peaks">${s}${big}</g>` : "";
  }

  // Colour ramp legend, clipped to the heights found in the current view's image.
  function legend(code) {
    const k = keyFor(last, code), top = k && INDEX[k] ? Math.max(300, INDEX[k].max) : 4000;
    const grad = RAMP.map(([m, c]) => `${c} ${(m / top * 100).toFixed(0)}%`).join(", ");   // stops past 100% are clipped
    const ticks = [0, Math.round(top / 2 / 100) * 100, Math.round(top / 100) * 100];
    return `<div class="ex-terrain-legend" aria-label="Ground height, 0 to ${fmt(top)} metres"><span class="lbl">Ground height</span>` +
      `<span class="bar" style="background:linear-gradient(90deg, ${grad})"></span>` +
      `<span class="ticks">${ticks.map(t => `<span>${fmt(t)} m</span>`).join("")}</span>` +
      `<span class="peak-key"><svg viewBox="-6 -6 12 10" width="11" height="9" aria-hidden="true"><path class="ex-peak" d="M0 -5L4.75 3.5L-4.75 3.5Z"/></svg> peak</span></div>`;
  }

  // Real height profile of a river from its `pf` ([[km, m], ...]), drawn like the Explore concept diagrams.
  function profileSvg(r) {
    const pf = r && r.pf;
    if (!pf || pf.length < 2) return "";
    const X0 = 30, X1 = 330, Y0 = 34, Y1 = 132;
    const L = pf[pf.length - 1][0] || r.L || 1;
    const top = pf[0][1], low = pf[pf.length - 1][1], drop = top - low;
    const span = Math.max(drop, 10);
    const px = km => X0 + (X1 - X0) * km / L, py = m => Y0 + (Y1 - Y0) * (top - m) / span;
    const d = pf.map(([km, m], i) => `${i ? "L" : "M"}${px(km).toFixed(1)} ${py(m).toFixed(1)}`).join("");
    const exag = Math.round((L * 1000 / (X1 - X0)) / (span / (Y1 - Y0)));
    const mouth = r.t ? "Tidal water" : r.f ? esc(r.f) : "Mouth";
    return `<svg viewBox="0 0 360 170" class="dg dg-anim ex-profile" role="img" aria-label="${esc(`${r.n}: falls ${fmt(drop)} m over ${fmt(L)} km`)}">` +
      `<rect width="360" height="170" fill="var(--dg-sky)" opacity=".3"/>` +
      `<path d="${d} L${X1} 160 L${X0} 160Z" fill="var(--dg-soil)" opacity=".55"/>` +
      `<path d="${d}" fill="none" stroke="var(--river)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>` +
      `<path class="flow" d="${d}" fill="none" stroke="var(--river-flow)" stroke-width="2.2" stroke-linecap="round" opacity=".9"/>` +
      `<g transform="translate(${X0} ${py(top).toFixed(1)})"><circle class="ripple" r="5" fill="none" stroke="var(--dg-water-deep)" stroke-width="1.4"/><circle r="4" fill="var(--surface)" stroke="var(--dg-water-deep)" stroke-width="2"/></g>` +
      `<text class="dg-name" x="${X0 + 10}" y="${(py(top) - 10).toFixed(1)}">Source · ${fmt(top)} m</text>` +
      `<text class="dg-name" x="${X1}" y="${(py(low) - 12).toFixed(1)}" text-anchor="end">${mouth} · ${fmt(low)} m</text>` +
      `<text class="dg-sub" x="${X0}" y="168">0 km</text><text class="dg-sub" x="${X1}" y="168" text-anchor="end">${fmt(L)} km</text>` +
      `<text class="dg-num" x="180" y="152" text-anchor="middle">${fmt(L)} km · falls ${fmt(drop)} m</text>` +
      (exag > 1 ? `<text class="dg-nts" x="352" y="16" text-anchor="end">not to scale · height ×${fmt(exag)}</text>` : "") +
      `</svg>`;
  }

  // The whole "Source to mouth" card, ready to drop in place of the drawn curve.
  function profileFigure(r) {
    const svg = profileSvg(r);
    if (!svg) return "";
    const pf = r.pf, L = pf[pf.length - 1][0], drop = pf[0][1] - pf[pf.length - 1][1];
    const half = pf.find(p => p[1] <= pf[0][1] - drop / 2), halfKm = half ? half[0] : L;
    const cap = `<b>${esc(r.n)}</b> rises at ${fmt(pf[0][1])} m and falls ${fmt(drop)} m over ${fmt(L)} km` +
      `${r.t ? " to tidal water" : r.f ? ` before joining ${esc(r.f)}` : ""}; half of that fall comes in the first ${fmt(halfKm)} km. ` +
      `Steep, fast headwaters stay cool and full of oxygen, which is where sensitive animals do best. ` +
      `<span class="meta">Heights sampled at 32 points along the river from an elevation grid (AWS Terrain Tiles, 60–240 m cells; finer for small streams).</span>`;
    return `<details class="ex-concept" open><summary>Source to mouth</summary><figure>${svg}<figcaption>${cap}</figcaption></figure></details>`;
  }

  window.EXTERRAIN = { load, layer, peaks, legend, profileSvg, profileFigure, key: code => keyFor(last, code) };
})();
