"""lens calibration from recorded outcomes: what actually happened to the
projects a lens scored. pure, no io.

this is the honest half of "does this lens work": observed scores next to
observed outcomes, with the sample size always in view. it never claims
prediction. a lens with four outcomes has four outcomes, and the reader
decides what that is worth."""

from ..schemas import BaseModel

ADVANCED = ("advanced", "funded")
REJECTED = ("rejected",)


class OutcomeGroup(BaseModel):
    outcomes: list[str]
    targets: int
    mean_weighted_total: float | None


class CriterionGap(BaseModel):
    criterion: str
    weight: float
    mean_advanced: float
    mean_rejected: float
    difference: float  # advanced minus rejected, in points on the 0..5 scale


class Calibration(BaseModel):
    lens_id: str
    min_sample: int
    recorded: int
    groups: list[OutcomeGroup]
    criterion_gaps: list[CriterionGap]
    reading: str  # plain words about what can and cannot be said


def calibrate(lens_id: str, rows: list[dict], min_sample: int = 3) -> Calibration:
    """rows: [{outcome, weighted_total, per_criterion: [{criterion, weight, score}]}].
    one row per target, latest outcome only."""
    recorded = len(rows)
    advanced_rows = [r for r in rows if r["outcome"] in ADVANCED]
    rejected_rows = [r for r in rows if r["outcome"] in REJECTED]
    groups = [
        OutcomeGroup(
            outcomes=list(ADVANCED),
            targets=len(advanced_rows),
            mean_weighted_total=(
                round(sum(r["weighted_total"] for r in advanced_rows) / len(advanced_rows), 2) if advanced_rows else None
            ),
        ),
        OutcomeGroup(
            outcomes=list(REJECTED),
            targets=len(rejected_rows),
            mean_weighted_total=(
                round(sum(r["weighted_total"] for r in rejected_rows) / len(rejected_rows), 2) if rejected_rows else None
            ),
        ),
    ]

    criterion_gaps: list[CriterionGap] = []
    enough = len(advanced_rows) >= min_sample and len(rejected_rows) >= min_sample
    if enough:
        by_name_adv: dict[str, list[float]] = {}
        by_name_rej: dict[str, list[float]] = {}
        weights: dict[str, float] = {}
        for r in advanced_rows:
            for c in r["per_criterion"]:
                by_name_adv.setdefault(c["criterion"], []).append(c["score"])
                weights[c["criterion"]] = c["weight"]
        for r in rejected_rows:
            for c in r["per_criterion"]:
                by_name_rej.setdefault(c["criterion"], []).append(c["score"])
                weights[c["criterion"]] = c["weight"]
        for name in sorted(set(by_name_adv) & set(by_name_rej)):
            mean_adv = sum(by_name_adv[name]) / len(by_name_adv[name])
            mean_rej = sum(by_name_rej[name]) / len(by_name_rej[name])
            criterion_gaps.append(
                CriterionGap(
                    criterion=name,
                    weight=weights[name],
                    mean_advanced=round(mean_adv, 2),
                    mean_rejected=round(mean_rej, 2),
                    difference=round(mean_adv - mean_rej, 2),
                )
            )
        criterion_gaps.sort(key=lambda g: (-g.difference, g.criterion))

    if recorded == 0:
        reading = "no outcomes recorded: this lens has not been checked against anything that happened yet"
    elif not enough:
        reading = (
            f"{recorded} outcome(s) recorded, and calibration needs at least {min_sample} in each group "
            f"({len(advanced_rows)} advanced or funded, {len(rejected_rows)} rejected). too few to say anything about the lens"
        )
    else:
        best = criterion_gaps[0] if criterion_gaps else None
        if best is None:
            reading = f"{recorded} outcomes recorded: the lens was scored against different criteria, so nothing compares"
        elif best.difference <= 0:
            reading = (
                f"{recorded} outcomes recorded: no criterion separated advanced projects from rejected ones. "
                "this lens scored both groups alike, which is worth knowing"
            )
        else:
            reading = (
                f"{recorded} outcomes recorded: advanced and funded projects scored {best.difference} points higher "
                f'on "{best.criterion}" on average. observed on this sample, not a prediction'
            )
    return Calibration(
        lens_id=lens_id,
        min_sample=min_sample,
        recorded=recorded,
        groups=groups,
        criterion_gaps=criterion_gaps,
        reading=reading,
    )
