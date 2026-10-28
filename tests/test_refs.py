"""Every finding cites its sources, and every cited key exists."""

from iwla_river.web import findings  # noqa: F401  (registers the findings)
from iwla_river.web.refs import REFS, link
from iwla_river.web.registry import FINDINGS


def test_every_ref_has_a_link_and_text():
    for k, r in REFS.items():
        assert r["kind"] in ("data", "method", "science"), k
        assert r["full"] and r["short"], k
        assert link(k).startswith("https://"), k


def test_every_finding_cites_known_sources():
    import inspect
    for f in FINDINGS:
        src = inspect.getsource(f.fn)
        if f.id == "references":
            continue
        assert "refs=[" in src, f"{f.section}/{f.id} cites nothing"
        for chunk in src.split("refs=[")[1:]:
            keys = [k.strip().strip('"') for k in chunk.split("]")[0].split(",") if k.strip()]
            assert keys, f"{f.section}/{f.id} has an empty source list"
            for k in keys:
                assert k in REFS, f"{f.section}/{f.id}: unknown source {k}"
