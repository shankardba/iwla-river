/* Explore: a workspace for investigating the Save Our Streams data by watershed.

   Map (left): where samples are taken (heat), and the watersheds inside the one you are in (rings),
   coloured by the measure you pick. Panel (right): that watershed's figures against its parent's,
   the watersheds or sites inside it, and, for a biological site, its survey history.

   Data: data/watersheds.json (regions to subbasins, heat cells), data/huc4/<code>.json (smaller
   units, sites, site histories; fetched as you zoom), data/search.json (fetched when you search),
   data/lower48.json (state outlines). Every place opens in Google Maps; no map tiles are loaded. */
(function () {
  "use strict";
  const root = document.getElementById("explorer");
  if (!root) return;
  const $ = sel => root.querySelector(sel);
  const LEVEL = { 0: "Country", 2: "Region", 4: "Subregion", 6: "Basin", 8: "Subbasin", 10: "Watershed", 12: "Subwatershed" };
  const CHILD = { 0: "regions", 2: "subregions", 4: "basins", 6: "subbasins", 8: "watersheds", 10: "subwatersheds", 12: "sites" };
  const CHAPTER = root.dataset.chapter;
  const W = 760, H = 520;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = v => v != null && !Number.isNaN(v);
  const fmt = n => num(n) ? Math.round(n).toLocaleString("en-US") : "—";
  const pct = v => num(v) ? `${Math.round(v * 100)}%` : "—";
  const pts = v => num(v) ? `${v > 0 ? "+" : ""}${Math.round(v * 100)} pts` : "—";
  const gmaps = (la, lo) => `https://www.google.com/maps/search/?api=1&query=${la.toFixed(4)},${lo.toFixed(4)}`;

  let W8 = {}, SITES = {}, SERIES = {}, GEO = null, HEAT = [], SEARCH = null;
  let cur = "", site = null, sortKey = "bv", sortDir = -1, kind = "all", colorBy = "gap", showRings = true;
  let view = "w", st = "", ST = {}, SGEO = null; const SHEAT = {};   // view by watersheds ("w") or states ("s"); st = state code
  const loaded = {};

  // ---------- data ----------
  const w = code => code ? W8[code] : W8[""];
  const kids = code => Object.keys(W8).filter(k => k.length === code.length + 2 && k.startsWith(code));
  const huc4 = code => code.slice(0, 4);
  const label = code => !code ? "United States" : ((w(code) || {}).n || `Unit ${code}`);

  async function ensure(code) {
    if (code.length < 4) return;
    const h = huc4(code);
    if (loaded[h]) return;
    loaded[h] = true;
    try {
      const d = await fetch(`data/huc4/${h}.json`).then(r => r.json());
      Object.assign(W8, d.w); SITES[h] = d.sites || []; Object.assign(SERIES, d.series || {});
    } catch (e) { SITES[h] = []; }
  }

  // ---------- projection ----------
  function albers(lat, lon) {
    const r = Math.PI / 180, f1 = 29.5 * r, f2 = 45.5 * r, f0 = 23 * r, n = (Math.sin(f1) + Math.sin(f2)) / 2;
    const c = Math.cos(f1) ** 2 + 2 * n * Math.sin(f1), rho0 = Math.sqrt(c - 2 * n * Math.sin(f0)) / n;
    const rho = Math.sqrt(c - 2 * n * Math.sin(lat * r)) / n, th = n * (lon + 96) * r;
    return [rho * Math.sin(th), rho0 - rho * Math.cos(th)];
  }

  // ---------- colour by ----------
  const COLOR_BY = {
    gap: { name: "Sensitive animals vs expected", get: x => x.g,
      bins: [[-Infinity, -0.04, "var(--bad)", "fewer than expected"], [-0.04, 0.04, "var(--grey)", "about as expected"], [0.04, Infinity, "var(--good)", "more than expected"]] },
    paved: { name: "Watershed paved", get: x => x.im,
      bins: [[0, 2, "var(--r1)", "under 2%"], [2, 5, "var(--r2)", "2–5%"], [5, 10, "var(--r3)", "5–10%"], [10, 25, "var(--r4)", "10–25%"], [25, Infinity, "var(--r5)", "25% or more"]] },
    chloride: { name: "Chloride (median)", get: x => x.cm,
      bins: [[0, 50, "var(--r1)", "under 50 mg/L"], [50, 100, "var(--r2)", "50–100"], [100, 230, "var(--r4)", "100–230"], [230, Infinity, "var(--r5)", "over 230 (EPA level)"]] },
    score: { name: "Score percentile", get: x => x.sp,
      bins: [[0, 35, "var(--bad)", "low (under 35)"], [35, 65, "var(--grey)", "middle"], [65, 101, "var(--good)", "high (65 and up)"]] },
    surveys: { name: "Biological surveys", get: x => x.bv,
      bins: [[1, 10, "var(--s1)", "1–9"], [10, 50, "var(--s2)", "10–49"], [50, 250, "var(--s3)", "50–249"], [250, Infinity, "var(--s4)", "250 or more"]] },
  };
  function colorOf(x) {
    const cb = COLOR_BY[colorBy], v = x ? cb.get(x) : null;
    if (!num(v) || (colorBy === "surveys" && !v)) return "var(--nodata)";
    const b = cb.bins.find(b => v >= b[0] && v < b[1]);
    return b ? b[2] : "var(--nodata)";
  }

  // ---------- sample types (heat) ----------
  const KINDS = [["all", "All samples"], ["bio", "Biological"], ["salt", "Salt"], ["no3", "Nitrate"], ["chem", "Other chemistry"]];
  const cellN = (c, k) => k === "bio" ? c[2] : k === "salt" ? c[3] : k === "no3" ? c[4] : k === "chem" ? c[5] : c[2] + c[3] + c[4] + c[5];
  const siteN = (t, k) => k === "bio" ? t[4] : k === "salt" ? (t[7] || 0) : k === "no3" ? (t[8] || 0) : k === "chem" ? (t[9] || 0) : t[4] + t[5];
  const kindWord = () => kind === "all" ? "samples" : `${KINDS.find(k => k[0] === kind)[1].toLowerCase()} samples`;

  // ---------- map ----------
  // ---------- boundaries ----------
  let GTOP = null; const GREG = {}, GSUB = {};
  async function ensureGeo(code) {
    const get = u => fetch(u).then(r => r.ok ? r.json() : {}).catch(() => ({}));
    if (!GTOP) GTOP = await get("data/geo/top.json");
    if (code.length >= 2 && !GREG[code.slice(0, 2)]) GREG[code.slice(0, 2)] = await get(`data/geo/r${code.slice(0, 2)}.json`);
    if (code.length >= 4 && !GSUB[code.slice(0, 4)]) GSUB[code.slice(0, 4)] = await get(`data/geo/s${code.slice(0, 4)}.json`);
  }
  const shape = c => !c ? null : c.length === 2 ? (GTOP || {})[c] : c.length === 4 ? (GREG[c.slice(0, 2)] || {})[c] : (GSUB[c.slice(0, 4)] || {})[c];

  function mapSvg(code) {
    const isSites = code.length === 12;
    const areas = isSites ? [] : kids(code).map(w).filter(x => x && !(code === "" && ["19", "20", "21", "22"].includes(x.c)));
    const withShape = areas.filter(x => shape(x.c));
    let sites = [];
    if (isSites) {
      sites = (SITES[huc4(code)] || []).filter(t => t[3] === code && siteN(t, kind) > 0).map(t => ({
        la: t[1], lo: t[2], id: t[0], bio: t[4] > 0, r: 3.5 + Math.min(6, Math.log2(1 + siteN(t, kind))),
        color: t[4] ? "var(--c4)" : "var(--heat)",
        tip: `${t[6] || "Site"}: ${t[4]} biological, ${t[5]} other surveys. ${t[4] ? "Click for its history." : "Click for Google Maps."}` }));
    }
    const inWs = code.length >= 4 ? (SITES[huc4(code)] || []).filter(t => t[3].startsWith(code)) : [];
    const heat = isSites ? [] : code.length >= 4
      ? inWs.filter(t => siteN(t, kind) > 0).map(t => ({ q: albers(t[1], t[2]), n: siteN(t, kind) }))
      : HEAT.filter(c => cellN(c, kind) > 0 && c[0] > 24 && c[0] < 50 && c[1] > -125 && c[1] < -66).map(c => ({ q: albers(c[0], c[1]), n: cellN(c, kind), cell: 1 }));
    // Frame: the country by its outline; anything smaller by its own boundary, or failing that its areas and sites.
    let fit;
    if (code === "" && GEO) fit = GEO.border.flat().map(([lo, la]) => albers(la, lo));
    else if (shape(code)) fit = shape(code).flat().map(([lo, la]) => albers(la, lo));
    else fit = withShape.flatMap(x => shape(x.c).flat().map(([lo, la]) => albers(la, lo))).concat(inWs.map(t => albers(t[1], t[2])), sites.map(t => albers(t.la, t.lo)));
    if (!fit.length) return `<div class="ex-empty">No ${kindWord()} here. Try another sample type.</div>`;
    const x0 = Math.min(...fit.map(q => q[0])), x1 = Math.max(...fit.map(q => q[0])), y0 = Math.min(...fit.map(q => q[1])), y1 = Math.max(...fit.map(q => q[1]));
    const span = Math.max(x1 - x0, (y1 - y0) * W / H, 0.002), sc = (W - (code === "" ? 16 : 40)) / span;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, X = q => W / 2 + (q[0] - cx) * sc, Y = q => H / 2 - (q[1] - cy) * sc;
    const pathOf = rings => rings.map(ring => {
      let d = "", last = null;
      ring.forEach(([lo, la], i) => {
        const q = albers(la, lo), x = X(q), y = Y(q);
        if (last && i < ring.length - 1 && Math.abs(x - last[0]) + Math.abs(y - last[1]) < 0.8) return;
        d += `${d ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`; last = [x, y];
      });
      return d + "Z";
    }).join("");
    // Where to put a name: the centre of the largest ring, in screen space.
    const anchor = rings => {
      let best = null, bestA = 0;
      rings.forEach(ring => {
        const pts = ring.map(([lo, la]) => { const q = albers(la, lo); return [X(q), Y(q)]; });
        let a = 0, sx = 0, sy = 0;
        for (let i = 0; i < pts.length - 1; i++) { const c = pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]; a += c; sx += (pts[i][0] + pts[i + 1][0]) * c; sy += (pts[i][1] + pts[i + 1][1]) * c; }
        if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = [sx / (3 * a), sy / (3 * a)]; }
      });
      return { p: best, area: bestA / 2 };
    };
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
    // watershed areas
    const labels = [];
    withShape.forEach(x => {
      const rings = shape(x.c), col = colorOf(x), ch = CHAPTER && CHAPTER.startsWith(x.c);
      s += `<a href="#w${x.c}" data-go="${x.c}" data-code="${x.c}" class="ex-area${ch ? " chapter" : ""}"><path d="${pathOf(rings)}" fill="${showRings ? col : "transparent"}" fill-rule="evenodd"><title>${esc(x.n || x.c)}: ${fmt(x.s)} sites, ${fmt(x.bv)} biological surveys${num(x.g) ? `, ${pts(x.g)} sensitive vs expected` : ""}. Click to zoom in.</title></path></a>`;
      const an = anchor(rings);
      if (an.p) labels.push({ x: an.p[0], y: an.p[1], area: an.area, n: x.n || x.c, ch });
    });
    // areas with no boundary on file fall back to rings at their sites' centre
    areas.filter(x => !shape(x.c) && num(x.la)).forEach(x => {
      const q = albers(x.la, x.lo), r = Math.min(24, 4 + Math.sqrt(x.s + x.bv) * 0.8);
      s += `<a href="#w${x.c}" data-go="${x.c}" data-code="${x.c}" class="ex-ring"><circle cx="${X(q).toFixed(1)}" cy="${Y(q).toFixed(1)}" r="${r.toFixed(1)}" fill="${colorOf(x)}" fill-opacity=".2" stroke="${colorOf(x)}" stroke-width="2"><title>${esc(x.n || x.c)}. Click to zoom in.</title></circle></a>`;
      labels.push({ x: X(q), y: Y(q) + r + 10, area: r * r * 3, n: x.n || x.c });
    });
    if (shape(code)) s += `<path class="ex-parent${isSites ? " fill" : ""}" d="${pathOf(shape(code))}" fill-rule="evenodd"/>`;
    if (heat.length) {
      const mx = Math.log(1 + Math.max(...heat.map(h => h.n)));
      const cellPx = code.length < 4 ? Math.max(1.6, Math.abs(X(albers(38, -96.25)) - X(albers(38, -96))) * 0.62) : 0;
      s += `<g class="ex-heat">`;
      heat.forEach(h => {
        const x = X(h.q), y = Y(h.q);
        if (x < -10 || x > W + 10 || y < -10 || y > H + 10) return;
        const f = Math.log(1 + h.n) / mx;
        s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(cellPx || 2 + 3 * f).toFixed(1)}" fill="var(--heat)" fill-opacity="${(0.2 + 0.7 * f).toFixed(2)}"/>`;
      });
      s += `</g>`;
    }
    s += "</g>";
    sites.forEach(it => {
      const q = albers(it.la, it.lo), x = X(q).toFixed(1), y = Y(q).toFixed(1), sel = site && String(it.id) === String(site);
      const dot = `<circle cx="${x}" cy="${y}" r="${(it.r + (sel ? 2 : 0)).toFixed(1)}" fill="${it.color}" fill-opacity=".9" stroke="${sel ? "var(--ink)" : "var(--surface)"}" stroke-width="${sel ? 3 : 1.2}"><title>${esc(it.tip)}</title></circle>` +
        (sel ? `<circle class="ex-chapter" cx="${x}" cy="${y}" r="${(it.r + 8).toFixed(1)}"/>` : "");
      s += it.bio ? `<a href="#s${it.id}@${code}" data-site="${it.id}" class="ex-site">${dot}</a>` : `<a href="${gmaps(it.la, it.lo)}" target="_blank" rel="noopener">${dot}</a>`;
    });
    // names: biggest areas first, skipped when they would collide or the area is too small to hold them
    const boxes = [], free = (bx, by, bw, bh) => !boxes.some(b => bx < b[0] + b[2] && bx + bw > b[0] && by < b[1] + b[3] && by + bh > b[1]);
    labels.sort((a, b) => (b.ch ? 1 : 0) - (a.ch ? 1 : 0) || b.area - a.area).forEach(l => {
      const nm = l.n.length > 24 ? l.n.slice(0, 23) + "…" : l.n, tw = nm.length * 6.3 + 8;
      if (l.area < tw * 14 * 0.6 && labels.length > 6 && !l.ch) return;
      const x = Math.min(W - tw / 2 - 2, Math.max(tw / 2 + 2, l.x)), y = Math.min(H - 6, Math.max(14, l.y + 4));
      if (!free(x - tw / 2, y - 11, tw, 14)) return;
      boxes.push([x - tw / 2, y - 11, tw, 14]);
      s += `<text class="ex-label${l.ch ? " ch" : ""}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="middle">${esc(nm)}</text>`;
    });
    return s + "</svg>";
  }

  function legend(code) {
    const parts = [];
    if (code === "st") {
      parts.push(`<span><i class="heat"></i>samples per ${st ? "5" : "25"} km cell, darker = more</span>`);
      if (showRings) { const cb = COLOR_BY[colorBy]; parts.push(`<span class="lg-title">States: ${esc(cb.name)}</span>` + cb.bins.map(b => `<span><i class="area" style="background:${b[2]}"></i>${esc(b[3])}</span>`).join("") + '<span><i class="area" style="background:var(--nodata)"></i>no data</span>'); }
      return parts.join("");
    }
    if (code.length < 12) parts.push(`<span><i class="heat"></i>${code.length < 4 ? "samples per 25 km cell" : "samples per site"}, darker = more</span>`);
    if (code.length === 12) parts.push('<span><i style="background:var(--c4)"></i>biological site (click for history)</span><span><i style="background:var(--heat)"></i>salt, nitrate or chemistry only</span>');
    else if (showRings) {
      const cb = COLOR_BY[colorBy];
      parts.push(`<span class="lg-title">Watersheds: ${esc(cb.name)}</span>` + cb.bins.map(b => `<span><i class="area" style="background:${b[2]}"></i>${esc(b[3])}</span>`).join("") + '<span><i class="area" style="background:var(--nodata)"></i>no data</span>');
    }
    return parts.join("");
  }

  // ---------- panel ----------
  function crumbs(code) {
    const out = [`<a href="#wUS" data-go="">United States</a>`];
    for (let d = 2; d <= code.length; d += 2) {
      const c = code.slice(0, d);
      out.push(d === code.length && !site ? `<span aria-current="location">${esc(label(c))}</span>` : `<a href="#w${c}" data-go="${c}">${esc(label(c))}</a>`);
    }
    return out.join('<span class="sep" aria-hidden="true">›</span>');
  }

  function card(title, value, sub, parentLine) {
    return `<div class="ex-card"><span class="ex-card-t">${title}</span><b>${value}</b>${sub ? `<span class="ex-card-s">${sub}</span>` : ""}${parentLine ? `<span class="ex-card-p">${parentLine}</span>` : ""}</div>`;
  }
  function trendPill(v) {
    if (!v) return '<span class="pill neutral">too few years to test a trend</span>';
    return `<span class="pill ${v === "improving" ? "good" : v === "declining" ? "bad" : "neutral"}">gap ${esc(v)}</span>`;
  }

  function cards(x, parent) {
    const pl = parent ? (view === "s" ? "United States" : label(cur.slice(0, -2) || "")) : "";
    const gapCls = !num(x.g) ? "neutral" : x.g < -0.04 ? "bad" : x.g > 0.04 ? "good" : "neutral";
    return `<div class="ex-cards">` +
      card("Sites with samples", fmt(x.s), `${fmt(x.bv)} biological surveys${x.fy ? `, ${x.fy}–${x.ly}` : ""}`, parent ? `${esc(pl)}: ${fmt(parent.s)} sites` : "") +
      card("Pollution-sensitive animals", num(x.so) ? pct(x.so) : "—", num(x.se) ? `expected ${pct(x.se)} · <span class="pill ${gapCls}">${pts(x.g)}</span>` : "no biological surveys",
           parent && num(parent.so) ? `${esc(pl)}: ${pct(parent.so)}` : "") +
      card("Watershed paved", num(x.im) ? `${x.im.toFixed(1)}%` : "—", num(x.fo) ? `${Math.round(x.fo)}% forest` : "", parent && num(parent.im) ? `${esc(pl)}: ${parent.im.toFixed(1)}%` : "") +
      card("Chloride, median", num(x.cm) ? `${Math.round(x.cm)} <small>mg/L</small>` : "—", num(x.cn) ? `${fmt(x.cn)} readings` : "no readings", parent && num(parent.cm) ? `${esc(pl)}: ${Math.round(parent.cm)} mg/L` : "") +
      `</div><div class="ex-trend">${trendPill(x.gv)}${num(x.gp) ? ` <span class="meta">p = ${x.gp.toFixed(3)}</span>` : ""}${num(x.nm) ? ` <span class="meta">Nitrate median ${x.nm} mg/L</span>` : ""}</div>`;
  }

  function measures(x, parent) {
    const rows = [
      ["Sites with samples", fmt(x.s), parent ? fmt(parent.s) : ""],
      ["Biological surveys", fmt(x.bv), parent ? fmt(parent.bv) : ""],
      ["Years of biology", x.fy ? `${x.fy}–${x.ly}` : "—", parent && parent.fy ? `${parent.fy}–${parent.ly}` : ""],
      ["Sensitive share found", pct(x.so), parent ? pct(parent.so) : ""],
      ["Expected for its setting", pct(x.se), parent ? pct(parent.se) : ""],
      ["Found minus expected", pts(x.g), parent ? pts(parent.g) : ""],
      ["Score percentile", num(x.sp) ? Math.round(x.sp) : "—", parent && num(parent.sp) ? Math.round(parent.sp) : ""],
      ["Paved or roofed", num(x.im) ? `${x.im.toFixed(1)}%` : "—", parent && num(parent.im) ? `${parent.im.toFixed(1)}%` : ""],
      ["Forest", num(x.fo) ? `${Math.round(x.fo)}%` : "—", parent && num(parent.fo) ? `${Math.round(parent.fo)}%` : ""],
      ["Chloride, median", num(x.cm) ? `${Math.round(x.cm)} mg/L` : "—", parent && num(parent.cm) ? `${Math.round(parent.cm)} mg/L` : ""],
      ["Nitrate, median", num(x.nm) ? `${x.nm} mg/L` : "—", parent && num(parent.nm) ? `${parent.nm} mg/L` : ""],
    ];
    return `<details class="ex-more"><summary>All measures, against ${esc(parent ? label(cur.slice(0, -2)) : "—")}</summary><div class="tbl"><table><thead><tr><th>Measure</th><th class="n">${esc(label(cur))}</th><th class="n">${parent ? esc(label(cur.slice(0, -2))) : ""}</th></tr></thead><tbody>` +
      rows.map(r => `<tr><td>${r[0]}</td><td class="n">${r[1]}</td><td class="n">${r[2]}</td></tr>`).join("") + `</tbody></table></div></details>`;
  }

  function kidTable(code) {
    if (code.length === 12) {
      const rows = (SITES[huc4(code)] || []).filter(t => t[3] === code && siteN(t, kind) > 0).sort((a, b) => b[4] - a[4] || b[5] - a[5]);
      if (!rows.length) return `<p class="meta">No ${kindWord()} at sites here.</p>`;
      return `<div class="tbl"><table class="ex-list"><thead><tr><th>Site</th><th class="n">Biological</th><th class="n">Other</th><th></th></tr></thead><tbody>` +
        rows.map(t => `<tr class="${t[4] ? "go" : ""}" ${t[4] ? `data-site="${t[0]}"` : ""}><td>${t[4] ? `<a href="#s${t[0]}@${code}" data-site="${t[0]}">${esc(t[6] || "Site")}</a>` : esc(t[6] || "Site")}</td>` +
          `<td class="n">${fmt(t[4])}</td><td class="n">${fmt(t[5])}</td><td><a class="maplink" href="${gmaps(t[1], t[2])}" target="_blank" rel="noopener" aria-label="Open in Google Maps">Map ↗</a></td></tr>`).join("") + "</tbody></table></div>";
    }
    // Name, biology, and the measure the rings are coloured by (when it is not already shown).
    const extra = { paved: ["im", "Paved", 1, v => num(v) ? v.toFixed(1) + "%" : "—"], chloride: ["cm", "Chloride", 1, v => num(v) ? Math.round(v) : "—"],
                    score: ["sp", "Score pct", 1, v => num(v) ? Math.round(v) : "—"], surveys: null, gap: null }[colorBy];
    const cols = [["n", "Name", 0], ["bv", "Bio surveys", 1], ["so", "Sensitive", 1], ["g", "vs exp.", 1]].concat(extra ? [extra] : []);
    const rows = kids(code).map(w).filter(Boolean).sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      if (!num(va) && typeof va !== "string") return 1; if (!num(vb) && typeof vb !== "string") return -1;
      return (va > vb ? 1 : va < vb ? -1 : 0) * sortDir;
    });
    if (!rows.length) return '<p class="meta">Nothing inside this unit has surveys.</p>';
    const head = cols.map(([k, h, n]) => `<th class="${n ? "n" : ""}" aria-sort="${sortKey === k ? (sortDir > 0 ? "ascending" : "descending") : "none"}"><button type="button" class="sort" data-sort="${k}">${h}${sortKey === k ? (sortDir > 0 ? " ▲" : " ▼") : ""}</button></th>`).join("");
    return `<div class="tbl"><table class="ex-list"><thead><tr>${head}</tr></thead><tbody>` + rows.map(x =>
      `<tr class="go" data-go="${x.c}" data-code="${x.c}"><td><span class="sw" style="border-color:${colorOf(x)}"></span><a href="#w${x.c}" data-go="${x.c}">${esc(x.n || x.c)}</a>${CHAPTER && CHAPTER.startsWith(x.c) ? ' <span class="pill accent">chapter</span>' : ""}</td>` +
      `<td class="n">${fmt(x.bv)}</td><td class="n">${pct(x.so)}</td><td class="n">${pts(x.g)}</td>${extra ? `<td class="n">${extra[3](x[extra[0]])}</td>` : ""}</tr>`).join("") +
      "</tbody></table></div>";
  }

  // ---------- site history ----------
  function spark(points, opts) {
    const Wd = 340, Hd = 120, L = 30, R = 8, T = 10, B = 22;
    if (!points.length) return "";
    const ts = points.map(p => Date.parse(p.x)), t0 = Math.min(...ts), t1 = Math.max(...ts) + 1;
    const ys = points.flatMap(p => [p.y, p.e]).filter(num), lo = opts.min ?? Math.min(...ys), hi = opts.max ?? Math.max(...ys);
    const X = t => L + (t - t0) / (t1 - t0 || 1) * (Wd - L - R), Y = v => T + (1 - (v - lo) / (hi - lo || 1)) * (Hd - T - B);
    let s = `<svg viewBox="0 0 ${Wd} ${Hd}" class="ex-spark" role="img" aria-label="${esc(opts.title)}">`;
    [lo, (lo + hi) / 2, hi].forEach(v => s += `<line class="grid" x1="${L}" x2="${Wd - R}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/><text class="t-axis" x="${L - 4}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${opts.fmt(v)}</text>`);
    const y0 = new Date(t0).getUTCFullYear(), y1 = new Date(t1).getUTCFullYear();
    [y0, y1].forEach((yy, i) => s += `<text class="t-axis" x="${i ? Wd - R : L}" y="${Hd - 6}" text-anchor="${i ? "end" : "start"}">${yy}</text>`);
    const ex = points.filter(p => num(p.e));
    if (ex.length) s += `<polyline fill="none" stroke="var(--muted)" stroke-width="1.4" stroke-dasharray="4 3" points="${ex.map(p => `${X(Date.parse(p.x)).toFixed(1)},${Y(p.e).toFixed(1)}`).join(" ")}"/>`;
    points.forEach(p => { if (num(p.y)) s += `<circle cx="${X(Date.parse(p.x)).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="3.6" fill="${p.c || "var(--accent)"}"><title>${p.x}: ${opts.fmt(p.y)}${num(p.e) ? `, expected ${opts.fmt(p.e)}` : ""}</title></circle>`; });
    return s + "</svg>";
  }

  function siteView(id, code) {
    const t = (SITES[huc4(code)] || []).find(r => String(r[0]) === String(id));
    const h = SERIES[String(id)] || [];
    if (!t) return '<p class="meta">This site could not be found.</p>';
    const forms = [...new Set(h.map(r => r[1]))];
    const sos = h.filter(r => r[1] === "SOS"), va = h.filter(r => r[1] !== "SOS");
    const gaps = h.filter(r => num(r[3]) && num(r[4])).map(r => r[3] - r[4]);
    const meanGap = gaps.length ? gaps.reduce((a, b) => a + b, 0) / gaps.length : null;
    let out = `<div class="ex-cards">` +
      card("Biological surveys", fmt(h.length), h.length ? `${h[0][0].slice(0, 4)}–${h.at(-1)[0].slice(0, 4)}` : "", forms.length ? forms.join(" and ") + " form" : "") +
      card("Sensitive share, average", pct(h.length ? h.reduce((a, r) => a + (r[3] || 0), 0) / h.length : null), num(meanGap) ? `vs expected: ${pts(meanGap)}` : "", "") + `</div>`;
    out += `<h3 class="ex-h">Share of groups found that are pollution-sensitive</h3><p class="meta">Dots: what each survey found. Dashed line: what the model expected for that survey's season and setting.</p>` +
      spark(h.map(r => ({ x: r[0], y: r[3], e: r[4] })), { min: 0, max: 1, fmt: v => `${Math.round(v * 100)}%`, title: "Sensitive share over time" });
    if (sos.length) out += `<h3 class="ex-h">SOS score</h3>` + spark(sos.map(r => ({ x: r[0], y: r[2] })), { min: 0, fmt: v => Math.round(v), title: "SOS score over time" });
    if (va.length) out += `<h3 class="ex-h">Virginia form score (0–12)</h3>` + spark(va.map(r => ({ x: r[0], y: r[2], c: "var(--c4)" })), { min: 0, max: 12, fmt: v => Math.round(v), title: "Virginia score over time" });
    out += `<details class="ex-more"><summary>Every survey (${h.length})</summary><div class="tbl"><table><thead><tr><th>Date</th><th>Form</th><th class="n">Score</th><th class="n">Sensitive</th><th class="n">Expected</th></tr></thead><tbody>` +
      h.slice().reverse().map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td class="n">${num(r[2]) ? r[2] : "—"}</td><td class="n">${pct(r[3])}</td><td class="n">${pct(r[4])}</td></tr>`).join("") + `</tbody></table></div></details>`;
    return out;
  }

  // ---------- states ----------
  async function ensureStates() { if (!SGEO) { try { SGEO = (await fetch("data/geo/states.json").then(r => r.json())).states; } catch (e) { SGEO = {}; } } }
  function inPoly(x, y, rings) {
    let hit = false;
    for (const ring of rings) for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < xj + (y - yj) * (xi - xj) / ((yi - yj) || 1e-12)) hit = !hit;
    }
    return hit;
  }
  function stateMap(abbr) {
    const all = Object.keys(SGEO || {});
    if (!all.length) return '<div class="ex-empty">State outlines could not be loaded.</div>';
    const own = abbr ? SGEO[abbr].r : null;
    const fit = (own || all.flatMap(k => SGEO[k].r)).flat().map(([lo, la]) => albers(la, lo));
    const x0 = Math.min(...fit.map(q => q[0])), x1 = Math.max(...fit.map(q => q[0])), y0 = Math.min(...fit.map(q => q[1])), y1 = Math.max(...fit.map(q => q[1]));
    const span = Math.max(x1 - x0, (y1 - y0) * W / H), sc = (W - (abbr ? 60 : 16)) / span;
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, X = q => W / 2 + (q[0] - cx) * sc, Y = q => H / 2 - (q[1] - cy) * sc;
    const pathOf = rings => rings.map(ring => {
      let d = "", last = null;
      ring.forEach(([lo, la], i) => { const q = albers(la, lo), x = X(q), y = Y(q); if (last && i < ring.length - 1 && Math.abs(x - last[0]) + Math.abs(y - last[1]) < 0.8) return; d += `${d ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`; last = [x, y]; });
      return d + "Z";
    }).join("");
    const centre = rings => {
      let best = null, A = 0;
      rings.forEach(r => {
        const p = r.map(([lo, la]) => { const q = albers(la, lo); return [X(q), Y(q)]; });
        let a = 0, sx = 0, sy = 0;
        for (let i = 0; i < p.length - 1; i++) { const c = p[i][0] * p[i + 1][1] - p[i + 1][0] * p[i][1]; a += c; sx += (p[i][0] + p[i + 1][0]) * c; sy += (p[i][1] + p[i + 1][1]) * c; }
        if (Math.abs(a) > A) { A = Math.abs(a); best = [sx / (3 * a), sy / (3 * a)]; }
      });
      return { p: best, area: A / 2 };
    };
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of ${abbr ? esc(SGEO[abbr].n) : "the states"}"><clipPath id="exclip"><rect width="${W}" height="${H}"/></clipPath><g clip-path="url(#exclip)">`;
    const labels = [];
    all.forEach(k => {
      const x = ST[k], here = k === abbr, show = !abbr || here;
      const fill = showRings && x ? colorOf(x) : "transparent";
      s += `<a href="#st-${k}" data-st="${k}" data-code="st-${k}" class="ex-area${here ? " chapter" : ""}${show ? "" : " dim"}"><path d="${pathOf(SGEO[k].r)}" fill="${show ? fill : "transparent"}" fill-rule="evenodd"><title>${esc(SGEO[k].n)}${x ? `: ${fmt(x.s)} sites, ${fmt(x.bv)} biological surveys${num(x.g) ? `, ${pts(x.g)} sensitive vs expected` : ""}` : ": no samples"}. Click to zoom in.</title></path></a>`;
      const c = centre(SGEO[k].r);
      if (c.p) labels.push({ x: c.p[0], y: c.p[1], area: c.area, n: abbr ? SGEO[k].n : k, here });
    });
    // Heat: 25 km cells for the country; 5 km cells inside a state.
    const step = abbr ? 0.05 : 0.25;
    const cells = (abbr ? SHEAT[abbr] || [] : HEAT).filter(c => cellN(c, kind) > 0 && c[0] > 24 && c[0] < 50 && c[1] > -125 && c[1] < -66);
    if (cells.length) {
      const mx = Math.log(1 + Math.max(...cells.map(c => cellN(c, kind))));
      const r = Math.max(1.6, Math.abs(X(albers(38, -96 - step)) - X(albers(38, -96))) * 0.62);
      s += `<g class="ex-heat">` + cells.map(c => { const q = albers(c[0], c[1]), f = Math.log(1 + cellN(c, kind)) / mx; return `<circle cx="${X(q).toFixed(1)}" cy="${Y(q).toFixed(1)}" r="${r.toFixed(1)}" fill="var(--heat)" fill-opacity="${(0.2 + 0.7 * f).toFixed(2)}"/>`; }).join("") + `</g>`;
    }
    s += "</g>";
    const boxes = [], free = (bx, by, bw, bh) => !boxes.some(b => bx < b[0] + b[2] && bx + bw > b[0] && by < b[1] + b[3] && by + bh > b[1]);
    labels.sort((a, b) => (b.here ? 1 : 0) - (a.here ? 1 : 0) || b.area - a.area).forEach(l => {
      const tw = l.n.length * 6.6 + 8;
      if (!l.here && l.area < tw * 12) return;
      if (l.x < tw / 2 || l.x > W - tw / 2 || l.y < 12 || l.y > H - 6 || !free(l.x - tw / 2, l.y - 7, tw, 14)) return;
      boxes.push([l.x - tw / 2, l.y - 7, tw, 14]);
      s += `<text class="ex-label${l.here ? " ch" : ""}" x="${l.x.toFixed(1)}" y="${(l.y + 4).toFixed(1)}" text-anchor="middle">${esc(l.n)}</text>`;
    });
    return s + "</svg>";
  }
  function stateTable(abbr) {
    if (abbr) {
      const rows = (ST[abbr] || {}).hb || [];
      if (!rows.length) return '<p class="meta">No samples in this state.</p>';
      return `<div class="tbl"><table class="ex-list"><thead><tr><th>Subbasin</th><th class="n">Sites here</th><th class="n">Bio surveys</th></tr></thead><tbody>` +
        rows.map(([h, n, b]) => `<tr class="go" data-go="${h}" data-view-to="w"><td><span class="sw" style="border-color:${colorOf(w(h))}"></span><a href="#w${h}" data-go="${h}" data-view-to="w">${esc(label(h))}</a></td><td class="n">${fmt(n)}</td><td class="n">${fmt(b)}</td></tr>`).join("") + "</tbody></table></div>";
    }
    const rows = Object.keys(ST).map(k => ST[k]).sort((a, b) => (num(b[sortKey]) ? b[sortKey] : -1) - (num(a[sortKey]) ? a[sortKey] : -1));
    return `<div class="tbl"><table class="ex-list"><thead><tr><th>State</th><th class="n">Sites</th><th class="n">Bio surveys</th><th class="n">Sensitive</th><th class="n">vs exp.</th></tr></thead><tbody>` +
      rows.map(x => `<tr class="go" data-st="${x.c}" data-code="st-${x.c}"><td><span class="sw" style="border-color:${colorOf(x)}"></span><a href="#st-${x.c}" data-st="${x.c}">${esc(x.n)}</a></td><td class="n">${fmt(x.s)}</td><td class="n">${fmt(x.bv)}</td><td class="n">${pct(x.so)}</td><td class="n">${pts(x.g)}</td></tr>`).join("") + "</tbody></table></div>";
  }
  async function renderStates(push) {
    await ensureStates();
    if (st && !SHEAT[st]) { try { SHEAT[st] = await fetch(`data/states/${st}.json`).then(r => r.json()); } catch (e) { SHEAT[st] = []; } }
    if (push) { try { history.replaceState(null, "", st ? `#st-${st}` : "#st"); } catch (e) { /* keep the old address */ } }
    const x = st ? ST[st] || {} : w("") || {}, parent = st ? w("") : null;
    $(".ex-map").innerHTML = stateMap(st);
    $(".ex-legend").innerHTML = legend("st");
    $(".ex-crumbs").innerHTML = st ? `<a href="#st" data-st="">United States</a><span class="sep" aria-hidden="true">›</span><span aria-current="location">${esc(x.n || st)}</span>` : `<span aria-current="location">United States</span>`;
    $(".ex-head").innerHTML = `<h2 class="ex-title">${esc(st ? x.n || st : "United States")}</h2><p class="ex-sub">${st ? `State · ${st}` : "By state"}</p>` +
      `<div class="ex-actions">${st ? `<button type="button" data-st="">↑ All states</button>` : `<button type="button" class="primary" data-st="MD">Maryland</button>`}` +
      `${st && num(x.la) ? `<a class="btn" href="${gmaps(x.la, x.lo)}" target="_blank" rel="noopener">Google Maps ↗</a>` : ""}</div>`;
    $(".ex-body").innerHTML = (st ? "" : `<p class="ex-intro">The same samples grouped by state. Click a state to zoom in; from a state, its subbasins open in the watershed view.</p>`) +
      cards(x, parent) + `<h3 class="ex-h">${st ? `Subbasins with samples in ${esc(x.n || st)}` : "States"} <span class="meta">${st ? "click to open in the watershed view" : "click a row to zoom in"}</span></h3>` + stateTable(st);
    $(".ex-panel").scrollTop = 0;
  }

  // ---------- render ----------
  async function render(push) {
    root.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
    if (view === "s") {
      $(".ex-tools-kind").innerHTML = KINDS.map(([k, t]) => `<button type="button" data-kind="${k}" aria-pressed="${k === kind}">${t}</button>`).join("");
      $(".ex-colorby").value = colorBy; $(".ex-colorby").disabled = !showRings; $(".ex-rings").checked = showRings;
      return renderStates(push);
    }
    await Promise.all([ensure(cur), ensureGeo(cur)]);
    if (push) { const h = site ? `#s${site}@${cur}` : `#w${cur || "US"}`; try { history.replaceState(null, "", h); } catch (e) { /* keep the old address */ } }
    const x = w(cur) || {}, parent = cur ? w(cur.slice(0, -2)) : null;
    $(".ex-tools-kind").innerHTML = KINDS.map(([k, t]) => `<button type="button" data-kind="${k}" aria-pressed="${k === kind}">${t}</button>`).join("");
    $(".ex-colorby").value = colorBy;
    $(".ex-colorby").disabled = cur.length === 12 || !showRings;
    $(".ex-rings").checked = showRings;
    $(".ex-map").innerHTML = mapSvg(cur);
    $(".ex-legend").innerHTML = legend(cur);
    $(".ex-crumbs").innerHTML = crumbs(cur);
    if (site) {
      const t = (SITES[huc4(cur)] || []).find(r => String(r[0]) === String(site)) || [];
      $(".ex-head").innerHTML = `<button type="button" class="ex-back" data-go="${cur}">← ${esc(label(cur))}</button>` +
        `<h2 class="ex-title">${esc(t[6] || "Biological site")}</h2><p class="ex-sub">Biological monitoring site · ${esc(label(cur))}</p>` +
        (t[1] ? `<div class="ex-actions"><a class="btn" href="${gmaps(t[1], t[2])}" target="_blank" rel="noopener">Open in Google Maps ↗</a></div>` : "");
      $(".ex-body").innerHTML = siteView(site, cur);
    } else {
      $(".ex-head").innerHTML = `<h2 class="ex-title">${esc(label(cur))}</h2>` +
        `<p class="ex-sub">${LEVEL[cur.length]}${cur ? ` · HUC ${cur}` : ""}</p>` +
        `<div class="ex-actions">${cur ? `<button type="button" data-go="${cur.slice(0, -2)}">↑ ${esc(cur.length > 2 ? label(cur.slice(0, -2)) : "United States")}</button>` : ""}` +
        `${CHAPTER && cur !== CHAPTER ? `<button type="button" class="primary" data-go="${CHAPTER}">Go to Great Seneca Creek</button>` : ""}` +
        `${num(x.la) && cur ? `<a class="btn" href="${gmaps(x.la, x.lo)}" target="_blank" rel="noopener">Google Maps ↗</a>` : ""}</div>`;
      $(".ex-body").innerHTML = (cur === "" ? `<p class="ex-intro">Shaded areas are the water-resource regions of the lower 48, coloured by the measure you pick; orange dots show where volunteers take samples. Click a region to zoom in, or search for a watershed or stream<span class="kbd-hint"> (press <kbd>/</kbd>)</span>.</p>` : "") +
        cards(x, parent) + `<h3 class="ex-h">${cur.length === 12 ? "Sites" : `${CHILD[cur.length][0].toUpperCase()}${CHILD[cur.length].slice(1)} inside`} <span class="meta">${cur.length === 12 ? "biological sites open their history" : "click a row to zoom in"}</span></h3>` +
        kidTable(cur) + (cur ? measures(x, parent) : "");
    }
    $(".ex-panel").scrollTop = 0;
  }
  function go(code) { cur = code; site = null; render(true); }
  function openSite(id, code) { cur = code; site = String(id); render(true); }

  // ---------- search ----------
  const box = $(".ex-search input"), list = $(".ex-results");
  let hits = [], active = -1;
  async function loadSearch() { if (!SEARCH) { try { SEARCH = await fetch("data/search.json").then(r => r.json()); } catch (e) { SEARCH = { w: [], s: [] }; } } }
  function search(q) {
    q = q.trim().toLowerCase();
    if (q.length < 2 || !SEARCH) { hits = []; return; }
    const score = n => { const t = n.toLowerCase(); return t.startsWith(q) ? 0 : t.includes(" " + q) ? 1 : t.includes(q) ? 2 : 9; };
    const ws = SEARCH.w.map(([c, n]) => ({ t: "w", c, n, k: score(n) + c.length / 100 })).filter(h => h.k < 9);
    const ss = SEARCH.s.map(([id, n, h]) => ({ t: "s", id, n, c: h, k: score(n) + 0.5 })).filter(h => h.k < 9);
    hits = ws.concat(ss).sort((a, b) => a.k - b.k).slice(0, 9);
  }
  function showHits() {
    active = -1;
    const q = box.value.trim();
    list.hidden = q.length < 2;
    list.innerHTML = hits.length ? hits.map((h, i) => `<li role="option" id="ex-hit-${i}" data-i="${i}"><b>${esc(h.n)}</b><span>${h.t === "w" ? `${LEVEL[h.c.length]} · HUC ${h.c}` : "Biological site"}</span></li>`).join("")
      : `<li class="none">No watershed or site matches “${esc(q)}”.</li>`;
    box.setAttribute("aria-expanded", String(!list.hidden));
  }
  function pick(i) {
    const h = hits[i]; if (!h) return;
    list.hidden = true; box.setAttribute("aria-expanded", "false"); box.value = ""; box.blur();
    if (h.t === "w") go(h.c); else openSite(h.id, h.c);
  }
  box.addEventListener("focus", loadSearch);
  box.addEventListener("input", async () => { await loadSearch(); search(box.value); showHits(); });
  box.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault(); if (!hits.length) return;
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + hits.length) % hits.length;
      list.querySelectorAll("li").forEach((li, i) => li.classList.toggle("on", i === active));
      box.setAttribute("aria-activedescendant", `ex-hit-${active}`);
    } else if (e.key === "Enter") { e.preventDefault(); pick(active >= 0 ? active : 0); }
    else if (e.key === "Escape") { list.hidden = true; box.setAttribute("aria-expanded", "false"); }
  });
  list.addEventListener("mousedown", e => { const li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); pick(Number(li.dataset.i)); } });
  box.addEventListener("blur", () => setTimeout(() => { list.hidden = true; box.setAttribute("aria-expanded", "false"); }, 150));
  document.addEventListener("keydown", e => {
    if (e.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) { e.preventDefault(); box.focus(); }
  });

  // ---------- events ----------
  root.addEventListener("click", e => {
    const k = e.target.closest("[data-kind]"); if (k) { kind = k.dataset.kind; render(false); return; }
    const v = e.target.closest("[data-view]"); if (v) { view = v.dataset.view; if (view === "s") st = ""; sortKey = "bv"; sortDir = -1; render(true); return; }
    const vt = e.target.closest("[data-view-to]"); if (vt) { e.preventDefault(); view = "w"; go(vt.dataset.go); return; }
    const sb = e.target.closest("[data-st]"); if (sb) { e.preventDefault(); view = "s"; st = sb.dataset.st; render(true); return; }
    const so = e.target.closest("[data-sort]"); if (so) { const key = so.dataset.sort; sortDir = sortKey === key ? -sortDir : key === "n" ? 1 : -1; sortKey = key; render(false); return; }
    if (e.target.closest(".maplink")) return;
    const siteEl = e.target.closest("[data-site]"); if (siteEl) { e.preventDefault(); openSite(siteEl.dataset.site, cur); return; }
    const g = e.target.closest("[data-go]"); if (g) { e.preventDefault(); go(g.dataset.go); }
  });
  root.addEventListener("change", e => {
    if (e.target.classList.contains("ex-colorby")) { colorBy = e.target.value; render(false); }
    if (e.target.classList.contains("ex-rings")) { showRings = e.target.checked; render(false); }
  });
  // A table row lights up its ring, and a ring its row.
  const hl = (code, on) => root.querySelectorAll(`[data-code="${code}"]`).forEach(el => el.classList.toggle("hl", on));
  root.addEventListener("mouseover", e => { const el = e.target.closest("[data-code]"); if (el) hl(el.dataset.code, true); });
  root.addEventListener("mouseout", e => { const el = e.target.closest("[data-code]"); if (el) hl(el.dataset.code, false); });

  function fromHash() {
    const t = location.hash.match(/^#st(?:-([A-Z]{2}))?$/);
    if (t) { view = "s"; st = t[1] || ""; return; }
    view = "w";
    const m = location.hash.match(/^#s(\d+)@(\d{12})$/), n = location.hash.match(/^#w(\d*|US)$/);
    if (m) { cur = m[2]; site = m[1]; } else { cur = n && n[1] !== "US" ? n[1] : ""; site = null; }
  }
  window.addEventListener("hashchange", () => { fromHash(); render(false); });

  fetch("data/lower48.json").then(r => r.json()).then(g => { GEO = g; if (Object.keys(W8).length) render(false); }).catch(() => {});
  fetch("data/watersheds.json").then(r => r.json()).then(d => {
    W8 = d.w; HEAT = d.heat || []; ST = d.st || {};
    fromHash(); render(false);
  }).catch(() => { $(".ex-map").innerHTML = '<div class="ex-empty">The watershed data could not be loaded.</div>'; });
})();
