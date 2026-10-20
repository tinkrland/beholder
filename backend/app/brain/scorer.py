"""the scorer: per-criterion scores, gaps ranked by weight times missing score,
weighted total, confidence driven by fact confidence and evidence kinds."""

from ..schemas import CriterionScore, FactOut, GapOut, LensOut, ScoreOut
from .retrieval import resolve_fact_ids, relevant_facts, render_facts


async def score_criterion(criterion, facts: list[FactOut], lens: LensOut, run) -> tuple[CriterionScore, GapOut | None]:
    picked = relevant_facts(f"{criterion.name} {criterion.description or ''} {criterion.strong_answer or ''}", facts, lens)
    out = await run(
        "score_criterion",
        {
            "criterion": criterion.name,
            "strong_answer": criterion.strong_answer or criterion.description or "",
            "facts": render_facts(picked),
        },
    )
    score = float(out.get("score", 0))
    score = max(0.0, min(5.0, score))
    rng = out.get("range")
    if criterion.subjective:
        if not rng:
            rng = [max(0.0, score - 1), min(5.0, score + 1)]
        rng = [max(0.0, float(rng[0])), min(5.0, float(rng[1]))]

    cs = CriterionScore(
        criterion=criterion.name,
        score=score,
        range=[float(rng[0]), float(rng[1])] if (criterion.subjective and rng) else None,
        reasoning=out.get("reasoning", ""),
        fact_ids=[f for f in out.get("fact_ids", []) if any(x.id == f for x in picked)],
        raise_by=out.get("raise_by"),
    )

    gap = None
    if score == 0 or not cs.fact_ids:
        gap = GapOut(
            id="",
            target_id="",
            criterion=criterion.name,
            weight=criterion.weight,
            missing=f"no fact supports {criterion.name}: {criterion.strong_answer or criterion.description or ''}".strip(),
            would_close=out.get("raise_by") or "provide evidence this criterion asks for",
        )
    return cs, gap


async def score_target(target_id: str, model_version_id: str, facts: list[FactOut], lens: LensOut, run) -> tuple[ScoreOut, list[GapOut]]:
    """scores every criterion, gathers gaps ranked by weight x missing score."""
    per_criterion: list[CriterionScore] = []
    gaps: list[GapOut] = []
    for c in lens.criteria:
        cs, gap = await score_criterion(c, facts, lens, run)
        per_criterion.append(cs)
        if gap:
            gaps.append(gap)

    weighted_total = sum(c.weight * s.score for c, s in zip(lens.criteria, per_criterion, strict=False))

    supporting = [f for s in per_criterion for f in facts if f.id in s.fact_ids]
    confidence = sum(f.confidence for f in supporting) / len(supporting) if supporting else 0.0

    gaps.sort(key=lambda g: g.weight * (5.0), reverse=True)

    score = ScoreOut(
        id="",
        target_id=target_id,
        model_version_id=model_version_id,
        per_criterion=per_criterion,
        weighted_total=round(weighted_total, 3),
        confidence=round(confidence, 3),
    )
    return score, gaps
