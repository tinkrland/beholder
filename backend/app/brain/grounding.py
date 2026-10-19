"""the grounding coverage check: the nine w's are the extraction map
(thewframework/), and this module measures how grounded the project model is
in each dimension. a dimension with no facts is silent, and silence is
information: it is surfaced, not smoothed over.

pure functions, no db, no model calls: grounding is arithmetic over facts."""

from ..schemas import FactOut

# dimension -> the fact kinds that speak to it, per thewframework/readme.md
DIMENSION_KINDS: dict[str, set[str]] = {
    "who": {"audience"},
    "what": {"capability", "mechanic", "differentiator", "pricing", "metric"},
    "when": {"maturity", "metric"},
    "where": {"platform", "constraint"},
    "why": {"constraint"},
    "why not": {"alternative", "constraint"},
    "world": {"alternative", "differentiator"},
    "way": {"maturity", "plan"},
    "wire": {"metric", "audience"},
}

DIMENSION_TITLES = {
    "who": "target audience and personas",
    "what": "product features and core value",
    "when": "timing, triggers and lifecycle",
    "where": "channels and deployment",
    "why": "the problem statement",
    "why not": "barriers, friction and objections",
    "world": "market landscape and competitors",
    "way": "roadmap, horizons and scope guard",
    "wire": "messaging, social layer and virality",
}

# what would close a silent dimension, per thewframework's dimension pages
WOULD_CLOSE = {
    "who": "a source that names the target audience or the first segment",
    "what": "a readme, docs, or manifest that states what the product does",
    "when": "a changelog, release tags, or dated docs that show lifecycle timing",
    "where": "deploy configs or platform docs that show where it runs and ships",
    "why": "a problem statement in the readme or positioning docs",
    "why not": "alternatives, prerequisites, or onboarding docs that name barriers",
    "world": "comparison docs, or stated alternatives and competitors",
    "way": "a roadmap, milestones, or non-goals that stage the work",
    "wire": "growth or positioning docs with stated messaging and loops",
}

DIMENSION_ORDER = ["who", "what", "when", "where", "why", "why not", "world", "way", "wire"]

# a fact counts toward grounding when it is confirmed, or when its confidence
# reaches this bar. evidence below the bar grounds partially: it exists, but
# it is not yet something a sentence can rest on.
GROUNDED_CONFIDENCE = 0.7


def _speaks_to(fact: FactOut, dimension: str) -> bool:
    kinds = DIMENSION_KINDS[dimension]
    if fact.kind in kinds:
        return True
    # why and wire also accept what the user states directly: your framing of
    # the problem and your own messaging voice are evidence about intent
    if dimension in ("why", "wire") and fact.kind in ("constraint", "metric") and fact.is_user_stated():
        return True
    return False


def ground(facts: list[FactOut]) -> dict:
    """returns a grounding report over the nine dimensions. statuses:
    grounded (a confirmed fact or one at/above the confidence bar),
    partial (facts exist, none reach the bar), silent (nothing speaks to it)."""
    usable = [f for f in facts if f.status != "rejected"]
    dimensions = []
    for dim in DIMENSION_ORDER:
        speaking = [f for f in usable if _speaks_to(f, dim)]
        best = max((f.confidence for f in speaking), default=0.0)
        has_confirmed = any(f.status == "confirmed" for f in speaking)
        if not speaking:
            status = "silent"
        elif has_confirmed or best >= GROUNDED_CONFIDENCE:
            status = "grounded"
        else:
            status = "partial"
        dimensions.append(
            {
                "dimension": dim,
                "focus": DIMENSION_TITLES[dim],
                "status": status,
                "fact_count": len(speaking),
                "fact_ids": [f.id for f in speaking],
                "kinds": sorted({f.kind for f in speaking}),
                "evidence_types": sorted({f.provenance[0].type for f in speaking if f.provenance}),
                "best_confidence": round(best, 3),
                "would_close": WOULD_CLOSE[dim] if status == "silent" else None,
            }
        )
    grounded = [d["dimension"] for d in dimensions if d["status"] == "grounded"]
    silent = [d["dimension"] for d in dimensions if d["status"] == "silent"]
    return {
        "dimensions": dimensions,
        "grounded": len(grounded),
        "partial": 9 - len(grounded) - len(silent),
        "silent": silent,
        "coverage": round(len(grounded) / 9, 3),
    }
