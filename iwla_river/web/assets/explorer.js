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
  let W8 = {}, SITES = {}, GEO = null, HEAT = [], cur = "", sortKey = "bv", sortDir = -1, kind = "all", showBubbles = true;
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

  // Sample types for the heat layer and filter. Cells: [lat, lon, bio, salt, nitrate, chem]; sites: [.., bio(4), other(5), .., salt(7), nitrate(8), chem(9)].
  const KINDS = [["all", "All samples"], ["bio", "Biological"], ["salt", "Salt (chloride)"], ["no3", "Nitrate"], ["chem", "Other chemistry"]];
  const cellN = (c, k) => k === "bio" ? c[2] : k === "salt" ? c[3] : k === "no3" ? c[4] : k === "chem" ? c[5] : c[2] + c[3] + c[4] + c[5];
  const siteN = (t, k) => k === "bio" ? t[4] : k === "salt" ? (t[7] || 0) : k === "no3" ? (t[8] || 0) : k === "chem" ? (t[9] || 0) : t[4] + t[5];

  function mapSvg(code) {
    let items = [], isSites = code.length === 12;
    if (isSites) {
      items = (SITES[huc4(code)] || []).filter(t => t[3] === code && siteN(t, kind) > 0)
        .map(t => ({ la: t[1], lo: t[2], r: 3 + Math.min(6, Math.log2(1 + siteN(t, kind))), color: t[4] ? "var(--c4)" : "var(--heat)", href: gmaps(t[1], t[2]),
                     tip: `${t[6] || "Site " + t[0]}: ${t[4]} biological, ${t[5]} other surveys. Click for Google Maps.` }));
    } else if (showBubbles) {
      items = kids(code).map(k => w(k)).filter(x => x && x.la != null && !(code === "" && ["19", "20", "21", "22"].includes(x.c)))
        .map(x => ({ la: x.la, lo: x.lo, code: x.c, r: Math.min(30, 4 + Math.sqrt(x.s + x.bv) * 0.9), color: gapColor(x),
                     tip: `${x.n || x.c} (${x.c}): ${fmt(x.s)} sites, ${fmt(x.bv)} biological surveys${x.g != null ? `, ${pts(x.g)} vs expected` : ""}. Click to zoom in.` }));
    }
    // Heat: quarter-degree cells for the country and regions; individual sites once inside a subregion.
    const inWs = code.length >= 4 ? (SITES[huc4(code)] || []).filter(t => t[3].startsWith(code)) : [];
    const heatPts = isSites ? [] : code.length >= 4
      ? inWs.filter(t => siteN(t, kind) > 0).map(t => ({ q: albers(t[1], t[2]), n: siteN(t, kind) }))
      : HEAT.filter(c => cellN(c, kind) > 0 && c[0] > 24 && c[0] < 50 && c[1] > -125 && c[1] < -66).map(c => ({ q: albers(c[0], c[1]), n: cellN(c, kind), c }));
    const p = items.map(i => albers(i.la, i.lo));
    const own = code.length === 2 ? kids(code).map(w).filter(x => x && x.la != null).map(x => albers(x.la, x.lo)) : [];
    const fit = code === "" && GEO ? GEO.border.flat().map(([lo, la]) => albers(la, lo))
      : p.concat(inWs.map(t => albers(t[1], t[2])), own);
    if (!fit.length) return `<p class="meta">No ${kind === "all" ? "" : KINDS.find(k => k[0] === kind)[1].toLowerCase() + " "}samples here.</p>`;
    let x0 = Math.min(...fit.map(q => q[0])), x1 = Math.max(...fit.map(q => q[0])), y0 = Math.min(...fit.map(q => q[1])), y1 = Math.max(...fit.map(q => q[1]));
    const span = Math.max(x1 - x0, (y1 - y0) * W / H, 0.004);
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, sc = (W - (code === "" ? 20 : 80)) / span;
    const X = q => W / 2 + (q[0] - cx) * sc, Y = q => H / 2 - (q[1] - cy) * sc;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of ${esc(label(code))}"><clipPath id="exclip"><rect width="${W}" height="${H}"/></clipPath><g clip-path="url(#exclip)">`;
    if (GEO) for (const part of ["inner", "border"]) for (const arc of GEO[part]) {
      let d = "", last = null, on = false;
      for (const [lo, la] of arc) {
        const q = albers(la, lo), x = X(q), y = Y(q);
        if (!(x > -60 && x < W + 60 && y > -60 && y < H + 60)) { on = false; continue; }
        if (last && on && Math.abs(x - last[0]) + Math.abs(y - last[1]) < 1.2) continue;
        d += `${on ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`; on = true; last = [x, y];
      }
      if (d.includes("L")) s += `<path d="${d}" fill="none" class="${part === "border" ? "map-border" : "map-state"}"/>`;
    }
    // heat layer
    if (heatPts.length) {
      const mx = Math.log(1 + Math.max(...heatPts.map(h => h.n)));
      const cellPx = code.length < 4 ? Math.max(1.6, Math.abs(X(albers(38, -96.25)) - X(albers(38, -96))) * 0.62) : 0;
      heatPts.forEach(h => {
        const x = X(h.q), y = Y(h.q);
        if (x < -10 || x > W + 10 || y < -10 || y > H + 10) return;
        const f = Math.log(1 + h.n) / mx;
        const r = cellPx || 2.2 + 3.5 * f;
        s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}" fill="var(--heat)" fill-opacity="${(0.18 + 0.72 * f).toFixed(2)}"><title>${fmt(h.n)} ${kind === "all" ? "samples" : KINDS.find(k => k[0] === kind)[1].toLowerCase() + " samples"}${h.c ? " in this 25 km cell" : " at this site"}</title></circle>`;
      });
    }
    s += "</g>";
    // watershed bubbles (rings, so the heat shows through) or sites, then labels that avoid each other
    const boxes = [];
    const free = (bx, by, bw, bh) => !boxes.some(b => bx < b[0] + b[2] && bx + bw > b[0] && by < b[1] + b[3] && by + bh > b[1]);
    items.forEach((it, i) => {
      const x = X(p[i]), y = Y(p[i]);
      const dot = isSites
        ? `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${it.r.toFixed(1)}" fill="${it.color}" fill-opacity=".8" stroke="var(--surface)" stroke-width="1"><title>${esc(it.tip)}</title></circle>`
        : `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${it.r.toFixed(1)}" fill="${it.color}" fill-opacity=".16" stroke="${it.color}" stroke-width="2"><title>${esc(it.tip)}</title></circle>`;
      s += it.href ? `<a href="${it.href}" target="_blank" rel="noopener">${dot}</a>` : `<a href="#w${it.code}" data-go="${it.code}">${dot}</a>`;
    });
    if (!isSites) {
      items.map((it, i) => [it, i]).sort((a, b) => b[0].r - a[0].r).forEach(([it, i]) => {
        if (!(items.length <= 15 || (it.r > 11 && items.length < 40))) return;
        const nm0 = (w(it.code) || {}).n || it.code, nm = nm0.length > 22 ? nm0.slice(0, 21) + "…" : nm0;
        const tw = nm.length * 6.4 + 6, x = X(p[i]), y = Y(p[i]);
        for (const ty of [y + it.r + 13, y - it.r - 5]) {
          if (free(x - tw / 2, ty - 11, tw, 14) && ty > 10 && ty < H - 2) {
            boxes.push([x - tw / 2, ty - 11, tw, 14]);
            s += `<text class="ex-label" x="${x.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="middle">${esc(nm)}</text>`;
            break;
          }
        }
      });
    }
    if (CHAPTER && CHAPTER.startsWith(code) && !isSites && showBubbles) {
      const ch = items.find(it => CHAPTER.startsWith(it.code));
      if (ch) { const q = albers(ch.la, ch.lo); s += `<circle cx="${X(q).toFixed(1)}" cy="${Y(q).toFixed(1)}" r="${(ch.r + 4).toFixed(1)}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>`; }
    }
    return s + "</svg>";
  }

  function controls() {
    return `<div class="ex-seg" role="group" aria-label="Sample type">${KINDS.map(([k, t]) => `<button type="button" data-kind="${k}" aria-pressed="${k === kind}">${t}</button>`).join("")}</div>` +
      `<label class="ex-toggle"><input type="checkbox" id="ex-bubbles" ${showBubbles ? "checked" : ""}> Watershed bubbles</label>`;
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
    root.querySelector(".ex-controls").innerHTML = controls();
    root.querySelector(".ex-map").innerHTML = mapSvg(code);
    root.querySelector(".ex-legend").innerHTML = code.length === 12
      ? '<span><i style="background:var(--c4)"></i>has biological surveys</span><span><i style="background:var(--heat)"></i>salt, nitrate or chemistry only</span><span class="meta">Size: samples. Click a site for Google Maps.</span>'
      : `<span><i class="heat"></i>${code.length < 4 ? "samples per 25 km cell" : "samples per site"}, darker = more</span>` +
        (showBubbles ? '<span><i class="ring" style="border-color:var(--bad)"></i>fewer sensitive animals than expected</span><span><i class="ring" style="border-color:var(--grey)"></i>about as expected</span><span><i class="ring" style="border-color:var(--good)"></i>more than expected</span><span><i class="ring" style="border-color:var(--c1)"></i>no biological surveys</span><span class="meta">Rings: watersheds inside this one. Click to zoom in.</span>' : "");
    root.querySelector(".ex-metrics").innerHTML = x ? metricRows(x, parent) : "";
    root.querySelector(".ex-kids-title").textContent = code.length >= 12 ? "Sites" : `${LEVEL[code.length + 2]}s inside`;
    root.querySelector(".ex-kids").innerHTML = kidTable(code);
  }

  root.addEventListener("change", e => {
    if (e.target.id === "ex-bubbles") { showBubbles = e.target.checked; go(cur, false); }
  });
  root.addEventListener("click", e => {
    const kb = e.target.closest("[data-kind]");
    if (kb) { kind = kb.dataset.kind; go(cur, false); return; }
    const s = e.target.closest("[data-sort]");
    if (s) { const k = s.dataset.sort; sortDir = sortKey === k ? -sortDir : (k === "n" ? 1 : -1); sortKey = k; root.querySelector(".ex-kids").innerHTML = kidTable(cur); return; }
    const t = e.target.closest("[data-go]");
    if (t) { e.preventDefault(); go(t.dataset.go); }
  });

  fetch("data/lower48.json").then(r => r.json()).then(g => { GEO = g; if (W8[""] !== undefined) go(cur, false); }).catch(() => {});
  fetch("data/watersheds.json").then(r => r.json()).then(d => {
    W8 = d.w;
    HEAT = d.heat || [];
    const h = (location.hash.match(/^#w(\d*|US)$/) || [])[1];
    go(h && h !== "US" ? h : "", false);
  }).catch(() => { root.querySelector(".ex-map").innerHTML = '<p class="meta">The watershed data could not be loaded.</p>'; });
})();
