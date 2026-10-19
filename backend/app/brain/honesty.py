"""the honesty guard: the check that makes beholder positioning instead of
marketing.

rules, per build-spec 7:
- every sentence in a view binds to at least one fact about the project, or to
  a lens criterion
- sentences bound to low-confidence unconfirmed facts are marked; export is
  blocked until the user confirms them
- the system never creates evidence: it can only point to a gap
"""

from ..schemas import FactOut, HonestyReport, PitchViewOut

CONFIRM_THRESHOLD = 0.7


def validate_view(view: PitchViewOut, facts: dict[str, FactOut]) -> HonestyReport:
    """exportable false means export is blocked. the reasons are listed so the
    user knows exactly what to fix: confirm a fact, or drop a sentence."""
    unbound = [s.id for s in view.sentences if not s.fact_ids and not s.criterion_ids]
    needs_confirmation: list[str] = []
    for s in view.sentences:
        for fid in s.fact_ids:
            f = facts.get(fid)
            if f and f.status != "confirmed" and f.confidence < CONFIRM_THRESHOLD:
                needs_confirmation.append(fid)
    needs_confirmation = sorted(set(needs_confirmation))

    blocking: list[str] = []
    if unbound:
        blocking.append(f"{len(unbound)} sentence(s) rest on no fact or criterion")
    if needs_confirmation:
        blocking.append(f"{len(needs_confirmation)} fact(s) need confirmation before export")

    return HonestyReport(
        exportable=not blocking,
        unbound_sentence_ids=unbound,
        needs_confirmation_fact_ids=needs_confirmation,
        blocking=blocking,
    )


def can_export(view: PitchViewOut, facts: dict[str, FactOut], confirmed_fact_ids: list[str]) -> HonestyReport:
    """export is blocked on honesty failures. the user may confirm facts at
    export time; confirmed facts lift the block. unbound sentences can never
    be confirmed into existence: they fail the render and stay dropped."""
    working = dict(facts)
    for fid in confirmed_fact_ids:
        if fid in working:
            working[fid] = working[fid].model_copy(update={"status": "confirmed"})
    return validate_view(view, working)
