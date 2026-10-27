/* Watershed explorer: zoom from the whole country into nested USGS hydrologic units and see each
   one's metrics next to its parent's. Data: data/watersheds.json (regions to subbasins) and
   data/huc4/<code>.json (watersheds, subwatersheds and sites), fetched when you zoom in.
   Every place opens in Google Maps; no map tiles are loaded. */
(function () {
  "use strict";
  const root = document.getElementById("explorer");
  if (!root) return;
  const LEVEL = { 0: "United States", 2: "Region", 4: "Subregion", 6: "Basin", 8: "Subbasin", 10: "Watershed", 12: "Subwatershed" };
  const CHAPTER = root.dataset.chapter;            // the chapter's HUC12
  const W = 760, H = 470;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = n => n == null || Number.isNaN(n) ? "—" : Math.round(n).toLocaleString("en-US");
  const pct = v => v == null || Number.isNaN(v) ? "—" : `${Math.round(v * 100)}%`;
  const pts = v => v == null || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${Math.round(v * 100)} pts`;
  const gmaps = (la, lo) => `https://www.google.com/maps/search/?api=1&query=${la.toFixed(4)},${lo.toFixed(4)}`;
  let W8 = {}, SITES = {}, GEO = null, cur = "", sortKey = "bv", sortDir = -1;
  const loaded = {};

  function albers(lat, lon) {
    const r = Math.PI / 180, f1 = 29.5 * r, f2 = 45.5 * r, f0 = 23 * r, n = (Math.sin(f1) + Math.sin(f2)) / 2;
    const c = Math.cos(f1) ** 2 + 2 * n * Math.sin(f1), rho0 = Math.sqrt(c - 2 * n * Math.sin(f0)) / n;
    const rho = Math.sqrt(c - 2 * n * Math.sin(lat * r)) / n, th = n * (lon + 96) * r;
    return [rho * Math.sin(th), rho0 - rho * Math.cos(th)];
  }
  const w = code => W8[code];
  const kids = code => Object.keys(W8).filter(k => k.length === (code.length || 0) + 2 && k.startsWith(code));
  const huc4 = code => code.slice(0, 4);

  async function ensure(code) {
    if (code.length < 4) return;
    const h = huc4(code);
    if (loaded[h]) return;
    try {
      const d = await fetch(`data/huc4/${h}.json`).then(r => r.json());
      Object.assign(W8, d.w);
      SITES[h] = d.sites;
    } catch (e) { SITES[h] = []; }
    loaded[h] = true;
  }

  function gapColor(x) {
    if (!x || x.g == null) return "var(--c1)";
    if (x.gv === "declining" || x.g < -0.04) return "var(--bad)";
    if (x.gv === "improving" || x.g > 0.04) return "var(--good)";
    return "var(--grey)";
  }
  function pill(v) {
    if (!v) return '<span class="pill neutral">no long record</span>';
    return `<span class="pill ${v === "improving" ? "good" : v === "declining" ? "bad" : "neutral"}">${esc(v)}</span>`;
  }
  function label(code) {
    if (!code) return "United States";
    const x = w(code);
    return (x && x.n) || `Unit ${code}`;
  }

  function crumbs(code) {
    const parts = [`<a href="#wUS" data-go="">United States</a>`];
    for (let d = 2; d <= code.length; d += 2) {
      const c = code.slice(0, d);
      parts.push(d === code.length ? `<span>${esc(label(c))}</span>` : `<a href="#w${c}" data-go="${c}">${esc(label(c))}</a>`);
    }
    return parts.join(' <span class="sep">›</span> ');
  }

  function metricRows(x, parent) {
    const rows = [
      ["Sites with surveys", fmt(x.s), parent ? fmt(parent.s) : ""],
      ["Biological surveys", fmt(x.bv), parent ? fmt(parent.bv) : ""],
      ["Years of biology", x.fy ? `${x.fy}–${x.ly}` : "—", parent && parent.fy ? `${parent.fy}–${parent.ly}` : ""],
      ["Sensitive share found", pct(x.so), parent ? pct(parent.so) : ""],
      ["Expected for its setting", pct(x.se), parent ? pct(parent.se) : ""],
      ["Found minus expected", pts(x.g), parent ? pts(parent.g) : ""],
      ["Trend in that gap", pill(x.gv) + (x.gp != null ? ` <span class="meta">p = ${x.gp.toFixed(3)}</span>` : ""), parent ? pill(parent.gv) : ""],
      ["Score percentile (within form)", x.sp == null ? "—" : Math.round(x.sp), parent && parent.sp != null ? Math.round(parent.sp) : ""],
      ["Watershed paved or roofed", x.im == null ? "—" : `${x.im.toFixed(1)}%`, parent && parent.im != null ? `${parent.im.toFixed(1)}%` : ""],
      ["Forest", x.fo == null ? "—" : `${Math.round(x.fo)}%`, parent && parent.fo != null ? `${Math.round(parent.fo)}%` : ""],
      ["Chloride, median (readings)", x.cm == null ? "—" : `${Math.round(x.cm)} mg/L (${fmt(x.cn)})`, parent && parent.cm != null ? `${Math.round(parent.cm)} mg/L` : ""],
      ["Nitrate, median (readings)", x.nm == null ? "—" : `${x.nm} mg/L (${fmt(x.nn)})`, parent && parent.nm != null ? `${parent.nm} mg/L` : ""],
    ];
    return `<table><thead><tr><th>Measure</th><th class="n">${esc(label(cur))}</th><th class="n">${parent ? esc(label(cur.slice(0, -2))) : ""}</th></tr></thead><tbody>` +
      rows.map(r => `<tr><td>${r[0]}</td><td class="n">${r[1]}</td><td class="n">${r[2]}</td></tr>`).join("") + "</tbody></table>";
  }

  function mapSvg(code) {
    let items, isSites = code.length === 12;
    if (isSites) {
      items = (SITES[huc4(code)] || []).filter(s => s[3] === code)
        .map(s => ({ la: s[1], lo: s[2], r: s[4] ? 6 : 3.5, color: s[4] ? "var(--c4)" : "var(--c1)", href: gmaps(s[1], s[2]),
                     tip: `${s[6] || "Site " + s[0]}: ${s[4]} biological, ${s[5]} other surveys. Click for Google Maps.` }));
    } else {
      items = kids(code).map(k => w(k)).filter(x => x && x.la != null && !(code === "" && ["19", "20", "21", "22"].includes(x.c)))
        .map(x => ({ la: x.la, lo: x.lo, code: x.c, r: Math.min(30, 4 + Math.sqrt(x.s + x.bv) * 0.9), color: gapColor(x),
                     tip: `${x.n || x.c} (${x.c}): ${fmt(x.s)} sites, ${fmt(x.bv)} biological surveys${x.g != null ? `, ${pts(x.g)} vs expected` : ""}. Click to zoom in.` }));
    }
    if (!items.length) return `<p class="meta">No sites to draw here.</p>`;
    // Inside a basin, every site in view is drawn faintly behind the bubbles to show the watershed's shape.
    const bg = !isSites && code.length >= 4 ? (SITES[huc4(code)] || []).filter(s => s[3].startsWith(code)) : [];
    const bgp = bg.map(s => albers(s[1], s[2]));
    const p = items.map(i => albers(i.la, i.lo));
    // The whole country is framed by its outline; smaller units by their own sites.
    const fit = code === "" && GEO ? GEO.border.flat().map(([lo, la]) => albers(la, lo)) : p.concat(bgp);
    let x0 = Math.min(...fit.map(q => q[0])), x1 = Math.max(...fit.map(q => q[0])), y0 = Math.min(...fit.map(q => q[1])), y1 = Math.max(...fit.map(q => q[1]));
    const span = Math.max(x1 - x0, (y1 - y0) * W / H, 0.004);
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, sc = (W - (code === "" ? 20 : 80)) / span;
    const X = q => W / 2 + (q[0] - cx) * sc, Y = q => H / 2 - (q[1] - cy) * sc;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of ${esc(label(code))}"><clipPath id="exclip"><rect width="${W}" height="${H}"/></clipPath><g clip-path="url(#exclip)">`;
    if (GEO) for (const kind of ["inner", "border"]) for (const arc of GEO[kind]) {
      let d = "", last = null, on = false;
      for (const [lo, la] of arc) {
        const q = albers(la, lo), x = X(q), y = Y(q);
        const vis = x > -60 && x < W + 60 && y > -60 && y < H + 60;
        if (!vis) { on = false; continue; }
        if (last && on && Math.abs(x - last[0]) + Math.abs(y - last[1]) < 1.2) continue;
        d += `${on ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`; on = true; last = [x, y];
      }
      if (d.includes("L")) s += `<path d="${d}" fill="none" class="${kind === "border" ? "map-border" : "map-state"}"/>`;
    }
    s += "</g>";
    bgp.forEach(q => s += `<circle cx="${X(q).toFixed(1)}" cy="${Y(q).toFixed(1)}" r="1.6" fill="var(--muted)" fill-opacity=".35"/>`);
    items.forEach((it, i) => {
      const dot = `<circle cx="${X(p[i]).toFixed(1)}" cy="${Y(p[i]).toFixed(1)}" r="${it.r.toFixed(1)}" fill="${it.color}" fill-opacity="${isSites ? 0.8 : 0.55}" stroke="var(--surface)" stroke-width="1"><title>${esc(it.tip)}</title></circle>`;
      s += it.href ? `<a href="${it.href}" target="_blank" rel="noopener">${dot}</a>` : `<a href="#w${it.code}" data-go="${it.code}">${dot}</a>`;
      if (!isSites && (items.length <= 15 || (it.r > 11 && items.length < 40))) {
        const nm = (w(it.code) || {}).n || it.code;
        s += `<text class="t-note" x="${X(p[i]).toFixed(1)}" y="${(Y(p[i]) + it.r + 12).toFixed(1)}" text-anchor="middle">${esc(nm.length > 22 ? nm.slice(0, 21) + "…" : nm)}</text>`;
      }
    });
    if (CHAPTER && CHAPTER.startsWith(code)) {
      const ch = isSites ? null : items.find(it => CHAPTER.startsWith(it.code));
      if (ch) { const q = albers(ch.la, ch.lo); s += `<circle cx="${X(q).toFixed(1)}" cy="${Y(q).toFixed(1)}" r="${(ch.r + 4).toFixed(1)}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>`; }
    }
    return s + "</svg>";
  }

  function kidTable(code) {
    if (code.length >= 12) {
      const rows = (SITES[huc4(code)] || []).filter(s => s[3] === code).sort((a, b) => b[4] - a[4] || b[5] - a[5]);
      return `<table><thead><tr><th>Site</th><th class="n">Biological</th><th class="n">Other surveys</th><th>Map</th></tr></thead><tbody>` +
        rows.map(s => `<tr><td>${esc(s[6] || "Site " + s[0])}</td><td class="n">${fmt(s[4])}</td><td class="n">${fmt(s[5])}</td><td><a href="${gmaps(s[1], s[2])}" target="_blank" rel="noopener">Google Maps</a></td></tr>`).join("") + "</tbody></table>";
    }
    const cols = [["n", "Name"], ["s", "Sites"], ["bv", "Biological surveys"], ["so", "Sensitive found"], ["se", "Expected"], ["g", "Gap"], ["gv", "Gap trend"], ["im", "Paved"], ["cm", "Chloride"]];
    const rows = kids(code).map(w).filter(Boolean).sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      if (va == null) return 1; if (vb == null) return -1;
      return (va > vb ? 1 : va < vb ? -1 : 0) * sortDir;
    });
    const head = cols.map(([k, h]) => `<th class="${k === "n" || k === "gv" ? "" : "n"} sortable" data-sort="${k}">${h}${sortKey === k ? (sortDir > 0 ? " ▲" : " ▼") : ""}</th>`).join("");
    const body = rows.map(x => `<tr class="go" data-go="${x.c}"><td><a href="#w${x.c}" data-go="${x.c}">${esc(x.n || x.c)}</a>${CHAPTER && CHAPTER.startsWith(x.c) ? ' <span class="pill neutral">chapter</span>' : ""}</td>` +
      `<td class="n">${fmt(x.s)}</td><td class="n">${fmt(x.bv)}</td><td class="n">${pct(x.so)}</td><td class="n">${pct(x.se)}</td><td class="n">${pts(x.g)}</td><td>${x.gv ? pill(x.gv) : ""}</td>` +
      `<td class="n">${x.im == null ? "—" : x.im.toFixed(1) + "%"}</td><td class="n">${x.cm == null ? "—" : Math.round(x.cm)}</td></tr>`).join("");
    return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  async function go(code, push = true) {
    await ensure(code);
    cur = code;
    if (push) { try { history.replaceState(null, "", `#w${code || "US"}`); } catch (e) { location.hash = `w${code || "US"}`; } }
    const x = code ? w(code) : W8[""];
    const parent = code ? (code.length > 2 ? w(code.slice(0, -2)) : W8[""]) : null;
    const lv = LEVEL[code.length];
    root.querySelector(".ex-crumbs").innerHTML = crumbs(code);
    root.querySelector(".ex-title").innerHTML = code ? `${esc(label(code))} <span class="meta">${lv} · HUC ${code}</span>` : "United States";
    root.querySelector(".ex-actions").innerHTML =
      (code ? `<button type="button" data-go="${code.slice(0, -2)}">Up to ${esc(code.length > 2 ? label(code.slice(0, -2)) : "United States")}</button>` : "") +
      (CHAPTER && cur !== CHAPTER ? `<button type="button" data-go="${CHAPTER}">Great Seneca Creek</button>` : "") +
      (x && x.la != null ? `<a class="btn" href="${gmaps(x.la, x.lo)}" target="_blank" rel="noopener">Open in Google Maps</a>` : "");
    root.querySelector(".ex-map").innerHTML = mapSvg(code);
    root.querySelector(".ex-legend").innerHTML = code.length === 12
      ? '<span><i style="background:var(--c4)"></i>has biological surveys</span><span><i style="background:var(--c1)"></i>salt, nitrate or chemistry only</span><span class="meta">Click a site for Google Maps</span>'
      : '<span><i style="background:var(--bad)"></i>fewer sensitive animals than expected</span><span><i style="background:var(--grey)"></i>about as expected</span><span><i style="background:var(--good)"></i>more than expected</span><span><i style="background:var(--c1)"></i>no biological surveys</span><span class="meta">Size: sites and surveys. Click to zoom in.</span>';
    root.querySelector(".ex-metrics").innerHTML = x ? metricRows(x, parent) : "";
    root.querySelector(".ex-kids-title").textContent = code.length >= 12 ? "Sites" : `${LEVEL[code.length + 2]}s inside`;
    root.querySelector(".ex-kids").innerHTML = kidTable(code);
  }

  root.addEventListener("click", e => {
    const s = e.target.closest("[data-sort]");
    if (s) { const k = s.dataset.sort; sortDir = sortKey === k ? -sortDir : (k === "n" ? 1 : -1); sortKey = k; root.querySelector(".ex-kids").innerHTML = kidTable(cur); return; }
    const t = e.target.closest("[data-go]");
    if (t) { e.preventDefault(); go(t.dataset.go); }
  });

  fetch("data/lower48.json").then(r => r.json()).then(g => { GEO = g; if (W8[""] !== undefined) go(cur, false); }).catch(() => {});
  fetch("data/watersheds.json").then(r => r.json()).then(d => {
    W8 = d.w;
    const h = (location.hash.match(/^#w(\d*|US)$/) || [])[1];
    go(h && h !== "US" ? h : "", false);
  }).catch(() => { root.querySelector(".ex-map").innerHTML = '<p class="meta">The watershed data could not be loaded.</p>'; });
})();
