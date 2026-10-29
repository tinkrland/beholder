"""the shared library: opt-in contribution, a human review gate, and a
public shelf. the rules that matter: confidential material is never
contributed, an unconfirmed parse is not a contribution, and a contributor
never reviews their own lens."""

import pytest

from app.config import settings
from app.service import contribute_lens, list_library, review_contributed_lens


def _lens(**kw):
    from app.models import Lens

    base = dict(
        type="rubric",
        name="cgu ethical ai rubric",
        review_status="confirmed",
        criteria=[{"name": "c", "weight": 1.0, "description": "", "strong_answer": "", "subjective": False, "inferred_weight": False}],
        sources=[{"kind": "pdf", "ref": "cgu-rubric.pdf"}],
        visibility="private",
        last_verified=None,
    )
    base.update(kw)
    return Lens(**base)


def _user(email, uid="u1"):
    from app.models import User

    return User(id=uid, email=email, auth_id=f"{uid}-auth")


@pytest.mark.asyncio
async def test_contribution_needs_a_public_ack(db_session):
    lens = _lens()
    with pytest.raises(ValueError, match="public"):
        await contribute_lens(db_session, lens, public_ack=False)


@pytest.mark.asyncio
async def test_unconfirmed_parse_is_not_a_contribution(db_session):
    with pytest.raises(ValueError, match="confirmed lens"):
        await contribute_lens(db_session, _lens(review_status="draft"), public_ack=True)


@pytest.mark.asyncio
async def test_custom_lenses_stay_private(db_session):
    with pytest.raises(ValueError, match="only uploaded rubrics"):
        await contribute_lens(db_session, _lens(type="custom"), public_ack=True)


@pytest.mark.asyncio
async def test_contribution_waits_for_review_and_is_not_twice(db_session):
    lens = _lens(owner_id="u1")
    db_session.add(lens)
    await db_session.flush()
    out = await contribute_lens(db_session, lens, public_ack=True)
    assert out.library_status == "submitted"
    assert out.visibility == "private"  # submitted is not public
    with pytest.raises(ValueError, match="already submitted"):
        await contribute_lens(db_session, lens, public_ack=True)


@pytest.mark.asyncio
async def test_no_reviewers_configured_approves_nothing(db_session, monkeypatch):
    monkeypatch.setattr(settings, "library_reviewers", "")
    lens = _lens(owner_id="u1", library_status="submitted")
    with pytest.raises(ValueError, match="no library reviewers"):
        await review_contributed_lens(db_session, lens, _user("someone@example.com"), "approve")


@pytest.mark.asyncio
async def test_only_allowlisted_reviewers_and_never_your_own(db_session, monkeypatch):
    monkeypatch.setattr(settings, "library_reviewers", "curator@example.com")
    lens = _lens(owner_id="u1", library_status="submitted")
    with pytest.raises(ValueError, match="not a library reviewer"):
        await review_contributed_lens(db_session, lens, _user("random@example.com"), "approve")
    # the contributor cannot review their own contribution, even if allowlisted
    monkeypatch.setattr(settings, "library_reviewers", "curator@example.com")
    with pytest.raises(ValueError, match="never reviews their own"):
        await review_contributed_lens(db_session, lens, _user("curator@example.com", uid="u1"), "approve")


@pytest.mark.asyncio
async def test_approve_makes_it_visible_reject_keeps_it_private(db_session, monkeypatch):
    monkeypatch.setattr(settings, "library_reviewers", "curator@example.com")
    curator = _user("curator@example.com", uid="u2")
    lens = _lens(owner_id="u1", library_status="submitted")
    db_session.add(lens)
    await db_session.flush()
    out = await review_contributed_lens(db_session, lens, curator, "approve")
    assert out.library_status == "approved"
    assert out.visibility == "shared"
    shelf = await list_library(db_session)
    assert [s["name"] for s in shelf] == ["cgu ethical ai rubric"]
    assert shelf[0]["sources"]  # cites its sources, so a reader can judge it

    other = _lens(owner_id="u3", name="someone else's rubric", library_status="submitted")
    db_session.add(other)
    await db_session.flush()
    out = await review_contributed_lens(db_session, other, curator, "reject")
    assert out.library_status == "rejected"
    assert out.visibility == "private"
    shelf = await list_library(db_session)
    assert [s["name"] for s in shelf] == ["cgu ethical ai rubric"]  # rejected is not public


@pytest.mark.asyncio
async def test_only_submitted_lenses_get_reviewed(db_session, monkeypatch):
    monkeypatch.setattr(settings, "library_reviewers", "curator@example.com")
    with pytest.raises(ValueError, match="only a submitted lens"):
        await review_contributed_lens(db_session, _lens(), _user("curator@example.com", uid="u2"), "approve")
