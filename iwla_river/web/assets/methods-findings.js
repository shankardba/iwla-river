/* The ten key findings on the Save Our Streams record, with how each was worked out (numbers from the site's own
   results, Clean Water Hub snapshot 2026-10-27). */
"use strict";
(() => {
const M = { bins: "Averages by bin", pairing: "Pairing", holdequal: "Holding other variables fixed", within: "Each site against itself",
  bootstrap: "Intervals", trend: "Trends", changepoint: "Change points", agreement: "Agreement", reliability: "Reliability",
  groupcv: "Prediction", clusters: "Types", needscore: "Need score" };
const F = [
  { status: "watch", title: "Paved watersheds lose sensitive animals", url: "national--paving.html",
    joined: "7,326 bug surveys at about 1,150 sites, each given its watershed's paved share from EPA StreamCat (NLCD 2019).",
    methods: ["bins"],
    numbers: "Sensitive share averages 40% in near-natural watersheds (0–2% paved, 3,021 surveys), 33% at 10–15%, and 22% where a quarter or more is paved (1,251 surveys).",
    limits: "Plain averages: no model, no uncertainty range, and nothing else held fixed. Losses start early, well before 25% paved." },
  { status: "good", title: "Volunteer chloride tracks agency lab chloride", url: "context--chloride-check.html",
    joined: "Each volunteer chloride reading paired with the median state or federal lab reading (Water Quality Portal) in the same small watershed (HUC12) within 7 days: 4,845 kit pairs at 377 sites, 3,887 Salt Watch strip pairs at 2,209 sites.",
    methods: ["pairing", "agreement", "bootstrap"],
    numbers: "Kit: correlation <span class=num>0.70 (0.58–0.79)</span>, 86% within a factor of two, median ratio 1.00. Strips: <span class=num>0.47 (0.37–0.59)</span>, 58% within two; in winter strips read higher (97 vs 80 mg/L, p &lt; 0.001). Intervals from 2,000 resamples of whole watersheds.",
    limits: "A watershed-and-week match is looser than the same spot, so the kit's true accuracy is likely better than shown. Strips read in coarse colour steps." },
  { status: "watch", title: "Chloride is rising at more sites than it is falling", url: "context--chloride-sites.html",
    joined: "39,690 volunteer chloride readings at 3,050 sites (2002–2026); zeros (likely blanks) and one impossible value dropped. Sites with 8+ readings over 4+ years: 396.",
    methods: ["trend"],
    numbers: "69 sites rising and 12 falling after the false-discovery-rate correction (q &lt; 0.05); 315 show no clear trend. Rising sites climb a median 6.3% a year.",
    limits: "The network-wide trend (−1% a decade, p = 0.10) is muddied by short-lived Salt Watch sites joining and leaving; the per-site count is the better measure." },
  { status: "", title: "Paved land, more than winter salt, tracks low bug scores", url: "context--development-salt.html",
    joined: "401 watershed-years in 140 small watersheds: spring bug scores (standardised within each form) against a winter salt index (lab chloride, gauge conductance and volunteer chloride, standardised and averaged) and paving from Annual NLCD.",
    methods: ["holdequal", "within"],
    numbers: "Salt alone: <span class=num>−0.37 SD</span> per SD of salt (p &lt; 0.001). With paving in the model: paving <span class=num>−0.5 SD per 10 points</span> (p &lt; 0.001), salt <span class=num>+0.03</span> (p = 0.71). Within a watershed, year to year: <span class=num>−0.09 (SE 0.08)</span>, p = 0.25.",
    limits: "This doesn't clear road salt: salt may be one of the ways paving harms streams, and paving and salt move together (r = 0.66). Spring surveys miss winter spikes; the site-scale finding below sees salt more directly." },
  { status: "concern", title: "Saltier streams hold fewer sensitive animals, well below EPA's chloride limit", url: "context--chloride-bugs.html",
    joined: "Rocky-bottom and original SOS bug surveys paired with the median volunteer chloride at the same site within 7 days: 644 surveys at 236 sites, only 8.8% of all surveys (30 days for change points: 735 at 254). Paving, season, state and form held fixed.",
    methods: ["pairing", "holdequal", "within", "changepoint", "bootstrap"],
    numbers: "Per tenfold chloride: sensitive share <span class=num>−6.2 points (−8.6 to −3.8)</span>, tolerant animals <span class=num>+6.9 (3.2 to 10.6)</span>, EPT <span class=num>−5.4 (−10.1 to −0.8)</span>. Within a site: no clear change (sensitive +0.7, p = 0.56). Scores step down at <span class=num>47 mg/L (25–54)</span> on the rocky-bottom form and <span class=num>60 (48–165)</span> on the original form, against EPA's chronic limit of 230. EPA's professional survey (8,752 visits) points the same way.",
    limits: "Salt and paving can't be fully separated (ρ 0.69), so other harms of development may ride along. Few samples above 230 mg/L. The link holds between sites, not within one: DataLab's engine rates it hinted." },
  { status: "", title: "Volunteers and professionals mostly agree, but volunteers rate generously", url: "context--volunteers-vs-professionals.html",
    joined: "Virginia volunteer surveys within 1 km of a Maryland state (MBSS) survey, and looser matches by watershed and year to MBSS and EPA's national survey; Maryland's own trained volunteers as a benchmark.",
    methods: ["agreement"],
    numbers: "Within 1 km: same Good/Fair/Poor class 67% of the time, weighted kappa <span class=num>0.50</span>, Spearman 0.71 (18 pairs at 7 sites), as good as Maryland's trained volunteers (kappa 0.36). Against EPA by watershed, volunteers rated higher 17 times and lower 9; 11 of 27 volunteer “Good” streams were Fair or Poor to EPA.",
    limits: "Same-spot, same-day pairs are rare; watershed matches add disagreement that isn't about skill. The rocky-bottom form tracks professionals far better than the original SOS count." },
  { status: "concern", title: "Most high-need watersheds have no volunteer monitor", url: "context--monitoring-gaps.html",
    joined: "22,697 small watersheds in the basins where volunteers work, scored from public maps (EPA impairments and permits, paving, mines); an active site is a bug survey since 2021.",
    methods: ["needscore"],
    numbers: "Of 1,093 watersheds with five or more pressures, 1,039 have no active bug site; 135 of those are within 25 km of one. Coverage rises with need but stays small: 0.6% at need 0–1, 5.3% at 6–9.",
    limits: "A simple count, deliberately. Monitored high-need watersheds are richer (median income $108k vs $92k, p = 0.02), which mostly follows where volunteers live." },
  { status: "", title: "Three surveys capture most of what a site is", url: "context--site-visits.html",
    joined: "7,332 surveys at 1,162 sites with a sensitive share (83% in Virginia); median two surveys per site, 468 surveyed once.",
    methods: ["reliability", "bootstrap"],
    numbers: "ICC <span class=num>0.64 (0.61–0.68)</span>: 64% of the variation is the site itself. The average of 3 surveys has reliability <span class=num>0.84 (0.82–0.86)</span>; 6 give 0.92, 10 give 0.95.",
    limits: "Mostly Virginia. Bringing a once-surveyed site to three surveys adds more than going from ten to twenty; detecting change over time needs more." },
  { status: "", title: "Maps predict about half of why sites differ; the rest is local", url: "context--maps-vs-local.html",
    joined: "The same 7,332 surveys with 20 mapped inputs (roads, septic, fertiliser, manure, paving and its change, permits, impairments, mines, flow, rain, heat, season, state); site averages use the 554 sites with 3+ surveys.",
    methods: ["groupcv"],
    numbers: "For sites the model never saw, R² for site averages: all inputs <span class=num>0.46 (0.40–0.48)</span>, land and pollution only 0.43, paved share alone 0.41, road density alone 0.29. Single surveys: 0.36.",
    limits: "Flow, weather and season add little. Roads and paving measure the same development (ρ 0.82), so neither should be read as the cause. The rest is local, plus survey noise." },
  { status: "concern", title: "Urban watersheds stand apart; livestock watersheds score like low-pressure ones", url: "context--watershed-types.html",
    joined: "286 small watersheds with 3+ bug surveys, described by the medians of 8 pressures (scaled robustly). The bugs are not used for grouping.",
    methods: ["clusters"],
    numbers: "Five stable types (silhouette 0.427, mean ARI 0.94). Median sensitive share: urban <span class=num>27%</span>, cropland 33%, mining 35%, low-pressure 40%, livestock 42%. Urban vs low-pressure q = 2.6e-14; livestock vs low-pressure q = 0.37 (no difference).",
    limits: "Livestock result is for these mostly Virginia watersheds, with manure estimated by county. Mining is tentative (least stable, borderline q). Cropland is all Midwest, so it also differs by region." },
];
const box = document.getElementById("cards");
const TAG = { good: "Good news", watch: "Watch", concern: "Concern", "": "Context" };
// Each finding starts as a closed tile (title, status, methods); opening it shows the joins, numbers and limits.
F.forEach((f) => {
  const d = document.createElement("details");
  d.className = `finding ${f.status}`;
  d.innerHTML = `<summary><span class="f-tag">${TAG[f.status]}</span><span class="f-title">${f.title}</span>
      <span class="f-methods">${f.methods.map((m) => M[m]).join(" → ")}</span>
      <a class="f-page" href="${f.url}">Finding page →</a></summary>
    <div class="f-body">
      <p><b>Joined.</b> ${f.joined}</p>
      <p><b>Methods.</b> ${f.methods.map((m) => `<a href="#m-${m}">${M[m]}</a>`).join(" → ")}</p>
      <p><b>Real numbers.</b> ${f.numbers}</p>
      <p class="f-limits"><b>Limits.</b> ${f.limits}</p>
      <p class="f-more"><a href="${f.url}">See the full finding, with its charts and sources →</a></p>
    </div>`;
  box.appendChild(d);
});
const all = document.getElementById("cards-all");
if (all) all.addEventListener("click", () => {
  const tiles = [...box.querySelectorAll("details")], open = !tiles.every((t) => t.open);
  tiles.forEach((t) => { t.open = open; });
  all.textContent = open ? "Close all" : "Open all";
});
})();
