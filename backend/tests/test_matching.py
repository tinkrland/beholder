"""matching: ranked scored targets and library suggestions by readiness.
matching never invents fit: a rank needs a score, a suggestion carries
readiness, and silence shows up as silence."""

from app.brain.matching import criteria_dimensions, match, preset_readiness, rank_scored, suggest_presets
from app.presets import load_presets


def _grounding(statuses: dict[str, str]) -> dict:
    """a grounding-shaped report with the given per-dimension statuses."""
    dims = [
        {"dimension": d, "status": s}
        for d, s in statuses.items()
    ]
    return {"dimensions": dims}


LOUD = _grounding({d: "grounded" for d in ["who", "what", "when", "where", "why", "why not", "world", "way", "wire"]})


def test_ranked_targets_order_by_weighted_total():
    ranked = rank_scored(
        [
            {"target_id": "b", "label": "grant committee reviewer", "weighted_total": 2.0, "confidence": 0.9},
            {"target_id": "a", "label": "yc application reader", "weighted_total": 3.5, "confidence": 0.7},
        ]
    )
    assert [r["target_id"] for r in ranked] == ["a", "b"]


def test_rank_ties_break_by_confidence_then_label():
    ranked = rank_scored(
        [
            {"target_id": "z", "label": "aaa", "weighted_total": 3.0, "confidence": 0.5},
            {"target_id": "x", "label": "bbb", "weighted_total": 3.0, "confidence": 0.9},
            {"target_id": "y", "label": "ccc", "weighted_total": 3.0, "confidence": 0.9},
        ]
    )
    assert [r["target_id"] for r in ranked] == ["x", "y", "z"]  # same score, confidence, then label


def test_rank_carries_top_gap_by_weight():
    ranked = rank_scored(
        [
            {
                "target_id": "a",
                "label": "yc",
                "weighted_total": 3.0,
                "top_gap": {"criterion": "traction", "weight": 0.3, "missing": "no metric", "would_close": "a launch metric"},
            }
        ]
    )
    assert ranked[0]["top_gap"]["criterion"] == "traction"


def test_criteria_dimensions_keyword_map():
    dims = criteria_dimensions({"name": "audience", "description": "names the first segment", "strong_answer": ""})
    assert dims == ["who"]
    dims = criteria_dimensions({"name": "deployment story", "description": "where does it run", "strong_answer": "docker"})
    assert dims == ["where"]


def test_criteria_dimensions_defaults_to_what():
    """a criterion that names no dimension still asks what the project is."""
    assert criteria_dimensions({"name": "overall", "description": "is it good"}) == ["what"]


def test_preset_readiness_counts_ready_criteria():
    preset = {
        "key": "t",
        "name": "t",
        "description": "",
        "criteria": [
            {"name": "audience", "weight": 0.5},  # who: loud
            {"name": "roadmap", "weight": 0.5},  # way: silent below
        ],
    }
    g = _grounding({"who": "grounded", "what": "grounded", "way": "silent"})
    r = preset_readiness(preset, g)
    assert r["ready_criteria"] == 1
    assert r["silent_dimensions"] == ["way"]
    assert "silence: way" in r["note"]


def test_suggestions_exclude_attached_and_rank_by_readiness():
    presets = load_presets()
    attached = {presets[0]["key"]}
    suggestions = suggest_presets(presets, LOUD, attached)
    keys = [s["key"] for s in suggestions]
    assert presets[0]["key"] not in keys
    ready = [s["ready_criteria"] for s in suggestions]
    assert ready == sorted(ready, reverse=True)
    assert all(s["note"] for s in suggestions)


def test_match_names_unscored_targets():
    report = match(
        [{"target_id": "a", "label": "yc", "weighted_total": 3.0}],
        [],
        LOUD,
        set(),
        [{"target_id": "b", "label": "grant committee reviewer"}],
    )
    assert [r["target_id"] for r in report["ranked"]] == ["a"]
    assert report["not_scored"] == [{"target_id": "b", "label": "grant committee reviewer"}]


def test_readiness_note_is_honest_when_all_ready():
    preset = {"key": "t", "name": "t", "description": "", "criteria": [{"name": "audience", "weight": 1.0}]}
    r = preset_readiness(preset, LOUD)
    assert r["silent_dimensions"] == []
    assert r["ready_criteria"] == 1
