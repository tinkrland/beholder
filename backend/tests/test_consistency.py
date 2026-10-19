"""consistency check tests: deterministic pairing, fair caps, verdict
filtering, and the honest empty report. no network, a canned runner."""

import pytest

from app.brain.consistency import check_consistency, cross_view_pairs, view_sentences


def _views():
    return [
        {"target_id": "t1", "label": "cgu", "sentences": [{"text": "the engine is deterministic"}, {"text": "we use no diffusion models"}]},
        {"target_id": "t2", "label": "ethglobal", "sentences": [{"text": "the engine renders in real time"}, {"text": "the scene is reproducible byte for byte"}]},
    ]


# ---------- pure pairing ----------

def test_view_sentences_extracts_text_idempotently():
    # stored views carry dicts; normalized views carry strings; junk is skipped
    view = {"sentences": [{"text": " a claim. ", "fact_ids": ["f1"]}, {"text": ""}, {"text": "another"}, "already normalized", 42]}
    assert view_sentences(view) == ["a claim.", "another", "already normalized"]
    assert view_sentences({"sentences": view_sentences(view)}) == view_sentences(view)  # idempotent


def test_pairs_cross_views_once_never_within():
    built = cross_view_pairs(_views())
    pairs = built["pairs"]
    assert pairs, "two views with sentences must produce pairs"
    for p in pairs:
        assert p["a"]["view"] != p["b"]["view"]  # never within one view


def test_identical_sentences_across_views_are_echoes_not_pairs():
    views = [
        {"target_id": "t1", "label": "a", "sentences": [{"text": "same truth"}]},
        {"target_id": "t2", "label": "b", "sentences": [{"text": "same truth"}, {"text": "a different claim"}]},
    ]
    built = cross_view_pairs(views)
    texts = [(p["a"]["text"], p["b"]["text"]) for p in built["pairs"]]
    assert ("same truth", "same truth") not in texts  # agreement, deduped
    assert ("same truth", "a different claim") in texts
    assert built["echoes"] == 1


def test_the_cap_round_robins_across_view_pairs():
    views = [
        {"target_id": "t1", "label": "a", "sentences": [{"text": f"a{i}"} for i in range(20)]},
        {"target_id": "t2", "label": "b", "sentences": [{"text": f"b{i}"} for i in range(20)]},
        {"target_id": "t3", "label": "c", "sentences": [{"text": "c0"}]},
    ]
    built = cross_view_pairs(views, max_pairs=6)
    assert len(built["pairs"]) == 6
    view_pairs = {(p["a"]["view"], p["b"]["view"]) for p in built["pairs"]}
    assert (0, 2) in view_pairs and (1, 2) in view_pairs  # the small view is not crowded out


def test_ordering_is_deterministic():
    first = [(p["a"]["text"], p["b"]["text"]) for p in cross_view_pairs(_views())["pairs"]]
    second = [(p["a"]["text"], p["b"]["text"]) for p in cross_view_pairs(_views())["pairs"]]
    assert first == second


# ---------- the check ----------

async def test_consistent_views_report_clean():
    async def run(task, payload):
        assert task == "check_consistency"
        n = payload["pairs"].count("[b]")
        return {"verdicts": [{"verdict": "consistent"} for _ in range(n)]}

    report = await check_consistency(_views(), run)
    assert report["consistent"] is True
    assert report["pairs_checked"] == 4 and report["contradictions"] == []


async def test_contradictions_carry_both_sides():
    async def run(task, payload):
        n = payload["pairs"].count("[b]")
        verdicts = [{"verdict": "consistent"} for _ in range(n)]
        verdicts[0] = {"verdict": "contradiction", "explanation": "one view says deterministic, the other promises generative ai"}
        return {"verdicts": verdicts}

    report = await check_consistency(_views(), run)
    assert report["consistent"] is False
    assert len(report["contradictions"]) == 1
    c = report["contradictions"][0]
    assert c["a"]["target_id"] in ("t1", "t2") and c["b"]["target_id"] in ("t1", "t2")
    assert c["a"]["target_id"] != c["b"]["target_id"]
    assert "deterministic" in c["explanation"]


async def test_sloppy_verdicts_can_only_underreport():
    async def run(task, payload):
        n = payload["pairs"].count("[b]")
        return {"verdicts": [{"verdict": "definitely bogus"} for _ in range(n)]}

    report = await check_consistency(_views(), run)
    assert report["consistent"] is True  # unknown verdicts become unrelated, never contradictions


async def test_fewer_than_two_views_is_an_honest_empty_report():
    async def run(task, payload):
        raise AssertionError("no model call should happen")

    one = [{"target_id": "t1", "label": "only", "sentences": [{"text": "a claim"}]}]
    report = await check_consistency(one, run)
    assert report["pairs_checked"] == 0 and report["consistent"] is True
    assert report["note"] == "fewer than two views with sentences: nothing to compare"
