"""the mvp flow, end to end, over http against the real app:

project -> text source -> extraction (three passes) -> rubric parse ->
mandatory review -> target -> score with gaps -> pitch view with sentence
binding -> overclaim check -> export blocked by the honesty guard ->
export allowed after confirmation.

the gateway is the mock provider with the canned responder; the database is
temp sqlite. no network, no keys.
"""

import pytest

from app.db import Base, engine
from app.main import app
from conftest import canned_responder


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # wire the mock provider with the canned responder onto the shared engine
        from app.config import settings

        settings.gateway_provider = "mock"
        import app.api.routes as routes

        original = routes.runner

        def mocked_runner(session):
            from app.gateway.runner import SimpleRunner
            from app.gateway import MockProvider

            return SimpleRunner(session, MockProvider(responder=canned_responder))

        routes.runner = mocked_runner
        yield c
        routes.runner = original
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_mvp_flow(client):
    # project
    r = await client.post("/api/projects", json={"name": "demo"})
    assert r.status_code == 200, r.text
    project_id = r.json()["id"]

    # text source
    r = await client.post(f"/api/projects/{project_id}/sources/text", json={"text": "the project renders the exact product mesh deterministically", "label": "readme"})
    assert r.status_code == 200, r.text

    # extraction: three passes, facts stored
    r = await client.post(f"/api/projects/{project_id}/extract")
    assert r.status_code == 200, r.text
    r = await client.get(f"/api/projects/{project_id}/facts")
    facts = r.json()
    assert len(facts) >= 1
    fact_ids = [f["id"] for f in facts]
    assert all(f["provenance"] for f in facts)  # no fact without provenance

    # grounding: the nine w's coverage check over the fact set
    r = await client.get(f"/api/projects/{project_id}/grounding")
    assert r.status_code == 200, r.text
    grounding = r.json()
    assert len(grounding["dimensions"]) == 9
    # the demo fact is a capability at 0.6 confidence: partial, not grounded
    what = next(d for d in grounding["dimensions"] if d["dimension"] == "what")
    assert what["status"] == "partial" and what["fact_count"] >= 1
    # dimensions nobody spoke to are named, with what would close them
    assert "who" in grounding["silent"]
    silent = next(d for d in grounding["dimensions"] if d["dimension"] == "who")
    assert silent["would_close"]

    # rubric parse -> draft lens
    r = await client.post("/api/lenses/parse-rubric", json={"text": "criteria: technical depth 30%, demo 30%, originality 20%, impact 20%", "source_ref": "sheet.pdf"})
    assert r.status_code == 200, r.text
    lens = r.json()
    assert lens["review_status"] == "draft"
    assert sum(c["weight"] for c in lens["criteria"]) == pytest.approx(1.0, abs=1e-3)

    # target
    r = await client.post(f"/api/projects/{project_id}/targets", json={"lens_id": lens["id"], "label": "hackathon x, main track"})
    target_id = r.json()["id"]

    # a draft lens never scores
    r = await client.post(f"/api/targets/{target_id}/score")
    assert r.status_code == 409

    # confirm the parse, then score
    r = await client.post(f"/api/lenses/{lens['id']}/confirm")
    assert r.status_code == 200
    r = await client.post(f"/api/targets/{target_id}/score")
    assert r.status_code == 200, r.text
    score = r.json()
    assert score["weighted_total"] == pytest.approx(0.3 * 4, abs=1e-6)  # only technical depth has support
    assert all(0 <= c["score"] <= 5 for c in score["per_criterion"])

    # gaps exist for unsupported criteria
    r = await client.get(f"/api/targets/{target_id}/gaps")
    gaps = r.json()
    assert any(g["criterion"] == "demo quality" for g in gaps)

    # pitch view: nine sections, sentences bound
    r = await client.post(f"/api/targets/{target_id}/pitch")
    assert r.status_code == 200, r.text
    view = r.json()
    assert len(view["sections"]) == 9
    bound = [s for s in view["sentences"] if s["fact_ids"] or s["criterion_ids"]]
    assert bound, "every surviving sentence must be bound"
    unbound = [s for s in view["sentences"] if not s["fact_ids"] and not s["criterion_ids"]]
    assert not unbound, "unbound sentences fail the render"

    # overclaim check on the user's own pitch language
    r = await client.post(f"/api/targets/{target_id}/check-claims", json={"pitch_text": "the engine never cracks and it scales to millions of users."})
    assert r.status_code == 200, r.text
    checks = r.json()
    assert all(c["verdict"] in ("supported", "partial", "unsupported", "contradicted") for c in checks)

    # export is blocked: the supporting facts are unconfirmed and low confidence
    r = await client.post(f"/api/views/{view['id']}/export", json={"format_id": "markdown"})
    assert r.status_code == 403
    assert "confirmation" in r.json()["detail"]

    # confirmation lifts the block: the honesty guard passes
    r = await client.post(f"/api/views/{view['id']}/export", json={"format_id": "markdown", "confirmed_fact_ids": fact_ids})
    assert r.status_code == 200, r.text
    assert "## one_liner" in r.json()["body"]


async def test_projects_of_others_do_not_exist_to_you(client):
    await client.post("/api/projects", json={"name": "mine"})
    # a second caller with a different dev identity
    other = client
    r = await other.get("/api/projects/demo-not-real/facts")
    assert r.status_code == 404  # cannot see what is not yours
