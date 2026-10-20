"""the fact editor: add, edit, confirm, reject. rejected facts never feed
the model, edited facts are confirmed by the human who edited them, and
views that rested on the old fact set are flagged stale, never silently
wrong."""

import pytest

from app.service import add_user_fact, edit_fact, load_facts_for_model, review_fact


class Body:
    def __init__(self, kind, statement, value=None, confidence=0.9):
        self.kind = kind
        self.statement = statement
        self.value = value
        self.confidence = confidence


async def _seed_facts(db_session, project_id, statements):
    from app.models import Fact
    from app.service import _content_hash
    from app.schemas import Provenance

    rows = []
    for st in statements:
        prov = [Provenance(type="user", ref="user")]
        row = Fact(
            project_id=project_id,
            kind="capability",
            statement=st,
            provenance=[p.model_dump() for p in prov],
            confidence=0.7,
            status="inferred",
            content_hash=_content_hash(st, prov),
        )
        db_session.add(row)
        rows.append(row)
    await db_session.flush()
    return rows


async def _project(db_session):
    from app.models import Project

    row = Project(name="test project")
    db_session.add(row)
    await db_session.flush()
    return row


@pytest.mark.asyncio
async def test_user_fact_is_confirmed_by_authorship(db_session):
    project = await _project(db_session)
    project_id = project.id
    row, stale = await add_user_fact(db_session, project_id, Body("capability", "ships as a docker image"))
    assert row.status == "confirmed"
    assert row.provenance[0]["type"] == "user"
    facts = await load_facts_for_model(db_session, project_id, None)
    assert any(f.statement == "ships as a docker image" and f.is_user_stated() for f in facts)


@pytest.mark.asyncio
async def test_edit_confirms_and_changes_hash(db_session):
    project = await _project(db_session)
    project_id = project.id
    from app.service import _content_hash
    from app.schemas import Provenance

    (fact,) = await _seed_facts(db_session, project_id, ["extracts facts from a repo"])
    old_hash = fact.content_hash
    row, stale = await edit_fact(db_session, fact.id, Body("capability", "extracts facts from github, gitlab, bitbucket, or gitea"))
    assert row.status == "confirmed"  # the human vouches for the edit
    assert row.statement == "extracts facts from github, gitlab, bitbucket, or gitea"
    expected = _content_hash(row.statement, [Provenance(**p) for p in row.provenance])
    assert row.content_hash == expected
    assert row.content_hash != old_hash


@pytest.mark.asyncio
async def test_rejected_fact_never_feeds_the_model(db_session):
    project = await _project(db_session)
    project_id = project.id
    await _seed_facts(db_session, project_id, ["fact a", "fact b"])
    facts = await load_facts_for_model(db_session, project_id, None)
    assert len(facts) == 2
    row, stale = await review_fact(db_session, facts[0].id, "rejected")
    assert row.status == "rejected"
    remaining = await load_facts_for_model(db_session, project_id, None)
    assert [f.statement for f in remaining] == ["fact b"]


@pytest.mark.asyncio
async def test_review_rejects_unknown_status(db_session):
    project = await _project(db_session)
    project_id = project.id
    (fact,) = await _seed_facts(db_session, project_id, ["fact a"])
    with pytest.raises(ValueError, match="confirmed or rejected"):
        await review_fact(db_session, fact.id, "maybe")


@pytest.mark.asyncio
async def test_confirm_vouches_for_the_statement(db_session):
    project = await _project(db_session)
    project_id = project.id
    (fact,) = await _seed_facts(db_session, project_id, ["fact a"])
    row, stale = await review_fact(db_session, fact.id, "confirmed")
    assert row.status == "confirmed"


@pytest.mark.asyncio
async def test_views_go_stale_when_facts_change(db_session):
    """the honesty loop: edit a fact, the views that rested on the old fact
    set are flagged, the next score speaks the new fact set."""
    from app.models import Lens, ModelVersion, PitchView, Target

    project = await _project(db_session)
    lens = Lens(
        type="custom",
        name="t",
        review_status="confirmed",
        criteria=[{"name": "c", "weight": 1.0, "description": "", "strong_answer": "", "subjective": False, "inferred_weight": False}],
        sources=[],
    )
    db_session.add(lens)
    await db_session.flush()
    target = Target(project_id=project.id, lens_id=lens.id, lens_version=1, label="t")
    db_session.add(target)
    version = ModelVersion(project_id=project.id, fact_ids=[], source_hashes=[])
    db_session.add(version)
    await db_session.flush()
    (fact,) = await _seed_facts(db_session, project.id, ["fact a"])
    view = PitchView(
        target_id=target.id,
        model_version_id=version.id,
        lens_version=1,
        sections=[],
        sentences=[],
        annotations=[],
        stale=False,
        cache_key="k",
    )
    db_session.add(view)
    await db_session.flush()

    _, stale = await edit_fact(db_session, fact.id, Body("capability", "a better statement"))
    assert stale == 1
    await db_session.refresh(view)
    assert view.stale is True
    _, stale = await review_fact(db_session, fact.id, "confirmed")
    assert stale == 0  # already flagged, not re-counted
