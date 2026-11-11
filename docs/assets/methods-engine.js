/* Small engine for stepped, animated method diagrams.
   Each diagram is a function (svg, h) -> steps; a step is {cap, run(t) or play(fast)}.
   - Static parts are drawn once in setup; steps only move or recolour a few marks (attribute writes, no layout reads).
   - Reduced motion: every tween jumps to its last frame.
   - Going back replays earlier steps instantly, then animates the chosen one. */
"use strict";

const NS = "http://www.w3.org/2000/svg";
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

function el(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs || {}) {
    if (k === "text") n.textContent = attrs[k];
    else n.setAttribute(k, attrs[k]);
  }
  if (parent) parent.appendChild(n);
  return n;
}

// seeded random numbers, so every reader sees the same illustrative data
function rng(seed) {
  let a = seed >>> 0;
  const r = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  r.norm = () => { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
  return r;
}

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const lerp = (a, b, t) => a + (b - a) * t;

// least squares slope and intercept
function fit(xs, ys) {
  const n = xs.length; let sx = 0, sy = 0;
  for (let i = 0; i < n; i++) { sx += xs[i]; sy += ys[i]; }
  const mx = sx / n, my = sy / n; let sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; }
  const b = sxx ? sxy / sxx : 0;
  return { b, a: my - b * mx, mx, my };
}
const pct = (arr, p) => { const s = [...arr].sort((a, b) => a - b); const i = (s.length - 1) * p; const lo = Math.floor(i); return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (i - lo); };
const median = (arr) => pct(arr, 0.5);

class Diagram {
  constructor(fig, build) {
    this.fig = fig;
    this.svg = fig.querySelector("svg");
    this.capEl = fig.querySelector(".cap");
    this.dots = fig.querySelector(".dots");
    this.btnPlay = fig.querySelector("[data-act=play]");
    this.gen = 0;          // bumps on every jump, so stale tweens stop
    this.i = -1;
    this.playing = false;
    this.build = build;
    this.reset();
    this.steps.forEach((s, k) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "dot"; b.setAttribute("aria-label", `Step ${k + 1}`);
      b.addEventListener("click", () => this.go(k));
      this.dots.appendChild(b);
    });
    fig.querySelector("[data-act=prev]").addEventListener("click", () => this.go(Math.max(0, this.i - 1)));
    fig.querySelector("[data-act=next]").addEventListener("click", () => this.go(Math.min(this.steps.length - 1, this.i + 1)));
    this.btnPlay.addEventListener("click", () => (this.playing ? this.pause() : this.play()));
    this.started = false;
    this.go(0);   // the first step is the still starting picture
  }
  reset() {
    this.svg.replaceChildren();
    this.h = { tween: (d, f) => this.tween(d, f), wait: (ms) => this.wait(ms) };
    this.steps = this.build(this.svg, this.h);
    this.i = -1;
  }
  tween(dur, f) {
    const g = this.gen;
    if (REDUCED || this.fast || dur <= 0) { f(1); return Promise.resolve(); }
    return new Promise((res) => {
      let t0 = null;
      const tick = (now) => {
        if (g !== this.gen) { f(1); return res(); }
        if (t0 === null) t0 = now;
        const t = Math.min(1, Math.max(0, (now - t0) / dur));
        f(ease(t));
        if (t < 1) requestAnimationFrame(tick); else res();
      };
      requestAnimationFrame(tick);
    });
  }
  wait(ms) {
    const g = this.gen;
    if (REDUCED || this.fast) return Promise.resolve();
    return new Promise((res) => setTimeout(() => res(g === this.gen), ms));
  }
  async run(k, fast) {
    this.fast = fast;
    this.capEl.innerHTML = this.steps[k].cap;
    await this.steps[k].play(this.h);
    this.fast = false;
  }
  async go(k, keepPlaying) {
    if (!keepPlaying) this.pause();
    this.gen++;
    const g = this.gen;
    if (k <= this.i) { this.reset(); for (let j = 0; j < k; j++) await this.run(j, true); }
    else for (let j = this.i + 1; j < k; j++) await this.run(j, true);
    this.i = k; this.mark();
    await this.run(k, false);
    return g === this.gen;
  }
  async play() {
    this.playing = true; this.btnPlay.textContent = "Pause"; this.btnPlay.setAttribute("aria-pressed", "true");
    if (this.i >= this.steps.length - 1) this.i = -1, this.reset();
    while (this.playing && this.i < this.steps.length - 1) {
      const ok = await this.go(this.i + 1, true);
      if (!ok || !this.playing) break;
      await this.wait(this.steps[this.i].hold ?? 1600);
    }
    if (this.i >= this.steps.length - 1) this.pause();
  }
  pause() { this.playing = false; this.btnPlay.textContent = "Play"; this.btnPlay.setAttribute("aria-pressed", "false"); }
  mark() {
    [...this.dots.children].forEach((d, k) => d.classList.toggle("on", k === this.i));
    this.fig.querySelector("[data-act=prev]").disabled = this.i <= 0;
    this.fig.querySelector("[data-act=next]").disabled = this.i >= this.steps.length - 1;
  }
}

// a scatter frame: axes, ticks and labels, with x/y scales; returns helpers
function frame(svg, o) {
  const { x0 = 70, y0 = 30, w = 560, h = 300, xd, yd, xl, yl, xt = [], yt = [] } = o;
  const g = el("g", { class: "axes" }, svg);
  const X = (v) => x0 + ((v - xd[0]) / (xd[1] - xd[0])) * w;
  const Y = (v) => y0 + h - ((v - yd[0]) / (yd[1] - yd[0])) * h;
  el("line", { x1: x0, y1: y0 + h, x2: x0 + w, y2: y0 + h, class: "ax" }, g);
  el("line", { x1: x0, y1: y0, x2: x0, y2: y0 + h, class: "ax" }, g);
  xt.forEach(([v, t]) => { el("line", { x1: X(v), x2: X(v), y1: y0 + h, y2: y0 + h + 5, class: "ax" }, g); el("text", { x: X(v), y: y0 + h + 19, class: "tick", "text-anchor": "middle", text: t }, g); });
  yt.forEach(([v, t]) => { el("line", { x1: x0 - 5, x2: x0, y1: Y(v), y2: Y(v), class: "ax" }, g); el("text", { x: x0 - 9, y: Y(v) + 4, class: "tick", "text-anchor": "end", text: t }, g); });
  if (xl) el("text", { x: x0 + w / 2, y: y0 + h + 40, class: "axl", "text-anchor": "middle", text: xl }, g);
  if (yl) el("text", { x: 18, y: y0 + h / 2, class: "axl", "text-anchor": "middle", transform: `rotate(-90 18 ${y0 + h / 2})`, text: yl }, g);
  return { X, Y, x0, y0, w, h, g };
}

window.SOS = { el, rng, ease, lerp, fit, pct, median, frame, Diagram, REDUCED };
