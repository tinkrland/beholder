"""the matcher: rank the targets a project has already scored, and suggest
library presets by evidence readiness.

matching never invents fit. the ranked list holds only targets with scores
on the table, ordered by weighted total. a suggestion carries readiness, not
fit: how many of the preset's criteria touch dimensions the project can
already speak to, and which would land on silence. the honest number comes
when the user runs the score.

pure functions, no db, no model calls: matching is arithmetic over scores
and grounding, the same honesty as the rest of beholder."""

from .grounding import DIMENSION_ORDER

# criterion text -> the dimensions it asks about. keyword matching is dumb
# on purpose: a criterion names its dimension in plain words ("audience",
# "deployment"), and a dumb map is auditable where a model call would be a
# second opinion pretending to be the first.
DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "who": ["audience", "user", "customer", "persona", "segment", "buyer", "icp", "reader"],
    "what": ["feature", "product", "capabilit", "core value", "function", "works", "demo", "use case"],
    "when": ["timing", "launch", "maturity", "stage", "lifecycle", "progress", "shipped", "traction"],
    "where": ["deploy", "platform", "distribution", "channel", "environment", "hosted", "stack", "integration", "where"],
    "why": ["problem", "pain", "need", "motivation", "frustration", "why"],
    "why not": ["barrier", "objection", "friction", "prerequisite", "risk", "resistance", "onboarding"],
    "world": ["competitor", "landscape", "alternative", "comparison", "differentiat", "market"],
    "way": ["roadmap", "milestone", "scope", "horizon", "future", "plan", "non-goal"],
    "wire": ["viral", "growth", "messaging", "social", "loop", "narrative", "word of mouth"],
}

# a criterion with no keyword hit still speaks to what: it asks what the
# project is, the default dimension of any judging question.
DEFAULT_DIMENSIONS = ("what",)


def criteria_dimensions(criterion: dict) -> list[str]:
    """the dimensions a criterion asks about, in dimension order. an empty
    list means the default: every criterion at least asks what this is."""
    text = " ".join(
        str(criterion.get(k) or "")
        for k in ("name", "description", "strong_answer")
    ).lower()
    dims = [d for d in DIMENSION_ORDER if any(k in text for k in DIMENSION_KEYWORDS[d])]
    return dims or list(DEFAULT_DIMENSIONS)


def rank_scored(scored: list[dict]) -> list[dict]:
    """targets with a latest score, best fit first. weighted total decides,
    confidence breaks ties, label breaks the rest: the order is deterministic
    and the same project always ranks the same way. unscored targets never
    appear here: an unscored target has no fit, and matching does not guess
    one."""
    ranked = sorted(
        scored,
        key=lambda r: (-r["weighted_total"], -r.get("confidence", 0.0), r.get("label", "")),
    )
    out = []
    for r in ranked:
        top_gap = r.get("top_gap")
        out.append(
            {
                "target_id": r["target_id"],
                "label": r.get("label", ""),
                "lens_id": r.get("lens_id"),
                "deadline": r.get("deadline"),
                "weighted_total": r["weighted_total"],
                "confidence": r.get("confidence", 0.5),
                "top_gap": top_gap,
            }
        )
    return out


def preset_readiness(preset: dict, grounding: dict) -> dict:
    """readiness, not fit: how many criteria touch dimensions the project
    can already speak to (grounded or partial), and which silent dimensions
    the preset would interrogate into a gap. a preset that would question
    only silence is still listed: silence is information, and the user
    deserves to see which criteria would land on it."""
    dims_status = {d["dimension"]: d["status"] for d in grounding["dimensions"]}
    criteria = preset["criteria"]
    ready = 0
    silent_dims: list[str] = []
    for c in criteria:
        touched = criteria_dimensions(c)
        if any(dims_status[d] != "silent" for d in touched):
            ready += 1
        for d in touched:
            if dims_status[d] == "silent" and d not in silent_dims:
                silent_dims.append(d)
    silent_dims = [d for d in DIMENSION_ORDER if d in silent_dims]

    if not silent_dims and ready == len(criteria):
        note = f"every criterion lands on dimensions the project can speak to"
    elif silent_dims:
        note = f"{ready} of {len(criteria)} criteria touch dimensions the project can speak to; " f"the rest would land on silence: {', '.join(silent_dims)}"
    else:
        note = f"{ready} of {len(criteria)} criteria touch dimensions the project can speak to"
    return {
        "key": preset["key"],
        "name": preset["name"],
        "description": preset["description"],
        "criteria_count": len(criteria),
        "ready_criteria": ready,
        "silent_dimensions": silent_dims,
        "note": note,
    }


def suggest_presets(presets: list[dict], grounding: dict, attached_keys: set[str]) -> list[dict]:
    """library presets not yet attached to the project, most ready first.
    attached presets are excluded: they are already targets, ranked or
    waiting for their score."""
    suggestions = [preset_readiness(p, grounding) for p in presets if p["key"] not in attached_keys]
    return sorted(suggestions, key=lambda s: (-s["ready_criteria"], s["key"]))


def match(scored: list[dict], presets: list[dict], grounding: dict, attached_keys: set[str], unscored: list[dict] | None = None) -> dict:
    """the matching report: ranked scored targets, preset suggestions, and
    targets attached but not yet scored, named so nothing hides. honest on
    both ends: a rank without a score never happens, and a suggestion
    without a readiness note never happens."""
    return {
        "ranked": rank_scored(scored),
        "suggestions": suggest_presets(presets, grounding, attached_keys),
        "not_scored": sorted(
            [{"target_id": t["target_id"], "label": t.get("label", "")} for t in (unscored or [])],
            key=lambda t: t["label"],
        ),
    }
