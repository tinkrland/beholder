"""the human-in-the-loop review contract: a draft lens is editable, a
confirmed lens is not, and confirmation must echo the current weights.
a review that never showed the numbers is not a review."""

import pytest

from app.service import confirm_lens_row, update_lens_draft


def _lens_row():
    from app.models import Lens

    return Lens(
        type="rubric",
        name="test rubric",
        review_status="draft",
        criteria=[
            {"name": "depth", "weight": 0.6, "description": "", "strong_answer": "", "subjective": False, "inferred_weight": True},
            {"name": "breadth", "weight": 0.4, "description": "", "strong_answer": "", "subjective": False, "inferred_weight": False},
        ],
        required_questions=[],
        required_artifacts=[],
        impresses=[],
        red_flags=[],
        alternatives_frame=None,
        trusted_evidence=[],
        objection_seeds=[],
        vocabulary=[],
        output_formats=[],
        sources=[],
        inferred_fields=["weights"],
    )


class EditIn:
    """the shape the route sends: criteria plus optional fields."""

    def __init__(self, criteria, **kw):
        from app.schemas import Criterion

        self.criteria = [Criterion(**c) if isinstance(c, dict) else c for c in criteria]
        for f in ("required_questions", "required_artifacts", "impresses", "red_flags", "alternatives_frame", "trusted_evidence", "objection_seeds", "vocabulary", "output_formats"):
            setattr(self, f, kw.get(f))


@pytest.mark.asyncio
async def test_edit_draft_changes_weight_and_unmarks_inferred(db_session):
    lens = _lens_row()
    edit = EditIn(
        [
            {"name": "depth", "weight": 0.7, "inferred_weight": True},
            {"name": "breadth", "weight": 0.3, "inferred_weight": False},
        ]
    )
    out = await update_lens_draft(db_session, lens, edit)
    assert [c["weight"] for c in out.criteria] == [0.7, 0.3]
    assert out.criteria[0]["inferred_weight"] is False  # the human set it
    assert out.criteria[1]["inferred_weight"] is False


@pytest.mark.asyncio
async def test_edit_rejects_wrong_weight_sum(db_session):
    lens = _lens_row()
    edit = EditIn(
        [
            {"name": "depth", "weight": 0.5, "inferred_weight": True},
            {"name": "breadth", "weight": 0.4, "inferred_weight": False},
        ]
    )
    with pytest.raises(ValueError, match="not 1.0"):
        await update_lens_draft(db_session, lens, edit)


@pytest.mark.asyncio
async def test_edit_rejects_empty_and_negative(db_session):
    with pytest.raises(ValueError, match="no criteria"):
        await update_lens_draft(db_session, _lens_row(), EditIn([]))
    edit = EditIn(
        [
            {"name": "depth", "weight": 1.2, "inferred_weight": True},
            {"name": "breadth", "weight": -0.2, "inferred_weight": False},
        ]
    )
    with pytest.raises(ValueError, match="positive weight"):
        await update_lens_draft(db_session, _lens_row(), edit)


@pytest.mark.asyncio
async def test_confirmed_lens_is_not_editable(db_session):
    lens = _lens_row()
    lens.review_status = "confirmed"
    with pytest.raises(ValueError, match="only a draft"):
        await update_lens_draft(db_session, lens, EditIn([{"name": "depth", "weight": 1.0}]))


@pytest.mark.asyncio
async def test_confirm_requires_echo_of_current_weights(db_session):
    lens = _lens_row()
    db_session.add(lens)
    await db_session.flush()  # column defaults (id, version) exist only after flush
    with pytest.raises(ValueError, match="name every criterion"):
        await confirm_lens_row(db_session, lens, [("depth", 0.6)])  # breadth missing
    out = await confirm_lens_row(db_session, lens, [("depth", 0.6), ("breadth", 0.4)])
    assert out.review_status == "confirmed"


@pytest.mark.asyncio
async def test_confirm_rejects_stale_echo(db_session):
    """the reviewer edited a weight, then confirmed the old numbers: the echo
    no longer matches what they reviewed, so it is a reject, never a guess."""
    lens = _lens_row()
    db_session.add(lens)
    await db_session.flush()
    with pytest.raises(ValueError, match="do not match"):
        await confirm_lens_row(db_session, lens, [("depth", 0.5), ("breadth", 0.5)])
