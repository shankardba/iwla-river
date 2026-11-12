"""Plain meanings of the technical terms used on finding pages.

The build lists, at the foot of each finding page, the terms that page uses (matched on the patterns below).
"""

import re

TERMS = [
    ("Seasonal Kendall test", r"[Ss]easonal Kendall",
     "A trend test that compares each season only with the same season in other years, so the usual swing between "
     "winter and summer is not mistaken for a trend."),
    ("Sen's slope", r"Sen('s)? slope",
     "The typical rate of change: the median of the slopes between every pair of same-season readings."),
    ("False discovery rate, q-value", r"false discovery|Benjamini|q-value|\bq &lt;|\bq below|\bq<",
     "A correction for testing many sites or animal groups at once. A q-value below 0.05 means that, among all the "
     "results called real, no more than about 5% are expected to be flukes."),
    ("p-value", r"\bp = |\bp &lt; |\bp-value|p &lt; 0",
     "How often a link at least this strong would turn up by chance if there were really none. Below 0.05 is "
     "usually taken to mean chance is an unlikely explanation."),
    ("95% interval", r"95% (interval|CI|range)|\(95% CI\)",
     "The range the true value very likely lies in, given the data. If it runs from below zero to above zero, the "
     "direction of the effect is not settled."),
    ("Rank correlation (Spearman)", r"[Rr]ank correlation|Spearman",
     "How closely two measures rise and fall together in rank order, from −1 (one always falls as the other rises) "
     "through 0 (no link) to 1."),
    ("Weighted kappa", r"kappa",
     "Agreement between two ways of rating the same stream, beyond what chance alone would give: 0 is chance, 1 is "
     "perfect agreement. Near misses (Good vs Fair) count less against it than wide misses."),
    ("Reliability", r"reliability",
     "How well the average of a few surveys predicts a site's long-run average, from 0 (not at all) to 1 (perfectly)."),
    ("Bootstrap", r"[Bb]ootstrap",
     "Re-running the analysis on many resamples of the data, taking whole sites at a time, to see how much the "
     "result could vary."),
    ("Change point", r"[Cc]hange point",
     "The chloride level at which the bug scores shift most sharply from one typical level to another."),
    ("Standard deviation (SD)", r"\bSD\b|standard deviation",
     "The typical spread of values around their average."),
    ("HUC12 watershed", r"HUC\s?12|HUC12s",
     "A small watershed in the USGS Watershed Boundary Dataset, named by a 12-digit hydrologic unit code; most "
     "cover 15 to 60 square miles."),
    ("EPA StreamCat", r"StreamCat",
     "EPA's dataset describing the land that drains to each stream reach: land cover, roads, permits, septic "
     "systems and more."),
    ("EPT", r"\bEPT\b",
     "Mayflies, stoneflies and caddisflies (Ephemeroptera, Plecoptera, Trichoptera): three groups that need clean "
     "water."),
]


def block(html: str) -> str:
    """The 'Terms used on this page' panel for a rendered finding page ('' when none apply)."""
    body = html.split('<section class="sources"')[0]
    body = re.sub(r"<[^>]+>", " ", body)
    found = [(name, words) for name, pat, words in TERMS if re.search(pat, body)]
    if not found:
        return ""
    items = "".join(f"<dt>{n}</dt><dd>{w}</dd>" for n, w in found)
    return f'<details class="method terms"><summary>Terms used on this page</summary><dl>{items}</dl></details>'
