"""the lens builder: rubric text in, draft lens out.

the parse is never trusted blindly: weights not stated in the source are
proposed equal and marked inferred_weight, and the whole draft carries
review_status draft. the mandatory review step lives in the api: a draft lens
never scores, and confirmation must name every inferred weight.
"""

from datetime import date

from ..schemas import Criterion, LensDraft


def _normalize_weights(criteria: list[Criterion]) -> list[Criterion]:
    """stated weights pass through. missing or malformed weights become equal
    shares, marked inferred. the caller (review step) sees exactly which
    weights are proposals."""
    missing = [c for c in criteria if not c.weight or c.weight <= 0]
    if missing:
        share = round(1.0 / len(criteria), 4) if len(missing) == len(criteria) else None
        for c in missing:
            c.inferred_weight = True
            if share:
                c.weight = share
            else:
                # some stated, some not: the unstated share the remainder
                stated = sum(c.weight for c in criteria if c.weight and c.weight > 0 and not c.inferred_weight)
                c.weight = round(max(0.0, 1.0 - stated) / len(missing), 4)
    # renormalize drift so the sum is exactly 1
    total = sum(c.weight for c in criteria)
    if total > 0:
        for c in criteria:
            c.weight = round(c.weight / total, 4)
    return criteria


async def parse_rubric(text: str, source_ref: str, run) -> LensDraft:
    out = await run("parse_rubric", {"source": source_ref, "text": text})
    criteria = [
        Criterion(
            name=c.get("name", "").strip(),
            weight=float(c.get("weight") or 0),
            description=c.get("description"),
            strong_answer=c.get("strong_answer"),
            subjective=bool(c.get("subjective", False)),
            inferred_weight=bool(c.get("inferred_weight", False)),
        )
        for c in out.get("criteria", [])
        if c.get("name")
    ]
    criteria = _normalize_weights(criteria)
    drafted = [f for f in ("impresses", "red_flags", "objection_seeds", "vocabulary", "output_formats", "trusted_evidence", "alternatives_frame") if out.get(f)]
    return LensDraft(
        type="rubric",
        name=out.get("name", "parsed rubric"),
        criteria=criteria,
        required_questions=out.get("required_questions", []),
        required_artifacts=out.get("required_artifacts", []),
        impresses=out.get("impresses", []),
        red_flags=out.get("red_flags", []),
        alternatives_frame=out.get("alternatives_frame"),
        trusted_evidence=out.get("trusted_evidence", []),
        objection_seeds=out.get("objection_seeds", []),
        vocabulary=out.get("vocabulary", []),
        output_formats=out.get("output_formats", []),
        sources=[{"type": "url" if source_ref.startswith("http") else "upload", "ref": source_ref}],
        inferred_fields=drafted,
        last_verified=date.today(),
    )


async def draft_custom_lens(description: str, run) -> LensDraft:
    out = await run("draft_lens", {"description": description})
    criteria = [
        Criterion(name=c.get("name", "").strip(), weight=0, description=c.get("description"), strong_answer=c.get("strong_answer"), subjective=bool(c.get("subjective", False)), inferred_weight=True)
        for c in out.get("criteria", [])
        if c.get("name")
    ]
    criteria = _normalize_weights(criteria)
    return LensDraft(
        type="custom",
        name=out.get("name", "custom reader"),
        criteria=criteria,
        sources=[{"type": "user", "ref": "user description"}],
        inferred_fields=["criteria", "impresses", "red_flags", "objection_seeds", "vocabulary", "output_formats"],
        last_verified=date.today(),
    )


def confirm_lens(lens) -> None:
    """the review step. flips a draft to confirmed. inferred weights stay marked:
    confirmation means a human read the proposals, not that they became stated."""
    if lens.review_status != "draft":
        return
    if not lens.criteria:
        raise ValueError("a lens with no criteria cannot be confirmed")
    lens.review_status = "confirmed"
