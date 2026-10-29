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

    # doc source: md parses locally, doc provenance
    r = await client.post(f"/api/projects/{project_id}/sources/doc", json={"filename": "growth.md", "text": "the icp names made-to-order jewelers as the beachhead"})
    assert r.status_code == 200, r.text

    # extraction: three passes, facts stored
    r = await client.post(f"/api/projects/{project_id}/extract")
    assert r.status_code == 200, r.text
    r = await client.get(f"/api/projects/{project_id}/facts")
    facts = r.json()
    assert len(facts) >= 1
    fact_ids = [f["id"] for f in facts]
    assert all(f["provenance"] for f in facts)  # no fact without provenance
    types = {f["provenance"][0]["type"] for f in facts}
    assert "doc" in types  # doc sources carry doc provenance

    # connected forge accounts: connect, masked listing, immediate revocation
    r = await client.put("/api/forge/accounts", json={"forge": "github", "token": "ghp_private_token"})
    assert r.status_code == 200, r.text
    r = await client.get("/api/forge/accounts")
    accounts = r.json()
    assert len(accounts) == 1 and accounts[0]["token_hint"] == "oken"
    assert all("token" not in a or a.get("token") != "ghp_private_token" for a in accounts)
    r = await client.delete("/api/forge/accounts/github")
    assert r.status_code == 200
    r = await client.get("/api/forge/accounts")
    assert r.json() == []

    # presets: authored lenses list with honest staleness, and score without
    # a review step because there was no parse
    r = await client.get("/api/presets")
    assert r.status_code == 200, r.text
    presets = r.json()
    yc = next(p for p in presets if p["key"] == "yc_application")
    assert yc["installed"] and yc["stale"] is True  # never verified: flagged, not hidden

    r = await client.post(f"/api/projects/{project_id}/targets/from-preset", json={"preset_key": "yc_application"})
    assert r.status_code == 200, r.text
    preset_target = r.json()
    assert preset_target["lens_version"] == 1

    # the preset target scores like any target
    r = await client.post(f"/api/targets/{preset_target['target_id']}/score")
    assert r.status_code == 200, r.text
    scored = r.json()
    assert scored["weighted_total"] >= 0 and scored["per_criterion"]

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
    assert r.status_code == 200, r.text
    target_id = r.json()["id"]

    # a draft lens never scores
    r = await client.post(f"/api/targets/{target_id}/score")
    assert r.status_code == 409

    # confirmation must echo the criteria: name and weight each, so the
    # reviewer saw every inferred weight. a blind button is not a review.
    r = await client.post(
        f"/api/lenses/{lens['id']}/confirm",
        json={"confirmed_criteria": [{"name": c["name"], "weight": c["weight"] - 0.1} for c in lens["criteria"]]},
    )
    assert r.status_code == 409  # the echo does not match the lens

    # the review's edit half: fix the parse before confirming. the weights
    # stay as parsed here: the score math below depends on them, and the
    # weight flip is covered in its own test.
    fixed = [dict(c) for c in lens["criteria"]]
    fixed[0]["description"] = "sharpened by the reviewer: what actually matters"
    r = await client.put(f"/api/lenses/{lens['id']}", json={"criteria": fixed})
    assert r.status_code == 200, r.text
    edited = r.json()
    assert edited["criteria"][0]["description"] == "sharpened by the reviewer: what actually matters"

    r = await client.post(
        f"/api/lenses/{lens['id']}/confirm",
        json={"confirmed_criteria": [{"name": c["name"], "weight": c["weight"]} for c in edited["criteria"]]},
    )
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

    # the second front gets its view too, so two views exist to compare
    r = await client.post(f"/api/targets/{preset_target['target_id']}/pitch")
    assert r.status_code == 200, r.text

    # the cross-view consistency check: one project, two views, one story
    r = await client.post(f"/api/projects/{project_id}/consistency")
    assert r.status_code == 200, r.text
    report = r.json()
    assert {v["target_id"] for v in report["checked_views"]} == {target_id, preset_target["target_id"]}
    assert report["pairs_checked"] > 0
    assert report["consistent"] is True  # the mock gateway votes consistent
    assert report["contradictions"] == []

    # matching: scored targets rank, presets suggest by readiness, nothing invents fit
    r = await client.get(f"/api/projects/{project_id}/matching")
    assert r.status_code == 200, r.text
    matching = r.json()
    assert {t["target_id"] for t in matching["ranked"]} == {target_id, preset_target["target_id"]}
    assert all("top_gap" in t for t in matching["ranked"])
    ranked_ids = [t["target_id"] for t in matching["ranked"]]
    expected = [t["target_id"] for t in sorted(matching["ranked"], key=lambda t: (-t["weighted_total"], -t["confidence"], t["label"]))]
    assert ranked_ids == expected  # order is deterministic: same input, same rank
    assert all(t["key"] != "yc_application" for t in matching["suggestions"])  # attached presets are never suggested
    assert all(t["note"] for t in matching["suggestions"])
    assert matching["not_scored"] == []  # both targets have scores on the table

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

    # more formats: the same honest sentences, rearranged for the moment.
    # an unknown format is a 400 naming what is known.
    r = await client.post(f"/api/views/{view['id']}/export", json={"format_id": "carrier_pigeon"})
    assert r.status_code == 400
    assert "demo_script" in r.json()["detail"]
    for fmt, marker in [
        ("demo_script", "demo script for"),
        ("deck_outline", "deck"),
        ("partner_one_pager", "one-pager"),
    ]:
        r = await client.post(f"/api/views/{view['id']}/export", json={"format_id": fmt, "confirmed_fact_ids": fact_ids})
        assert r.status_code == 200, r.text
        assert marker in r.json()["body"]

    # the fact editor: add a user-stated fact, edit an extracted one, reject
    # a third. views that rested on the old fact set are flagged stale, and
    # a rejected fact never feeds the model again.
    r = await client.post(
        f"/api/projects/{project_id}/facts",
        json={"kind": "capability", "statement": "the maintainer ships weekly", "confidence": 0.9},
    )
    assert r.status_code == 200, r.text
    user_fact = r.json()["fact"]
    assert user_fact["status"] == "confirmed"
    assert user_fact["provenance"][0]["type"] == "user"
    assert r.json()["stale_views"] >= 1  # views that rested on the old fact set

    fact_list = (await client.get(f"/api/projects/{project_id}/facts")).json()
    victim = next(f for f in fact_list if f["id"] != fact_list[0]["id"])
    r = await client.put(f"/api/facts/{victim['id']}", json={"kind": victim["kind"], "statement": "edited by the reviewer: " + victim["statement"]})
    assert r.status_code == 200, r.text
    assert r.json()["fact"]["status"] == "confirmed"
    assert r.json()["stale_views"] == 0  # already flagged by the add, not re-counted

    r = await client.post(f"/api/facts/{fact_list[0]['id']}/review", json={"status": "rejected"})
    assert r.status_code == 200, r.text
    assert r.json()["fact"]["status"] == "rejected"
    after = (await client.get(f"/api/projects/{project_id}/facts")).json()
    assert any(f["status"] == "rejected" for f in after)  # still in the editor, undoable

    # a re-score speaks the new fact set: the rejected fact is out
    r = await client.post(f"/api/targets/{target_id}/score")
    assert r.status_code == 200, r.text

    # model versioning: re-extract with a new source, the diff names what
    # changed. identity is the content hash, so re-derived facts are not
    # churn, and review actions show as status changes.
    r = await client.post(f"/api/projects/{project_id}/sources/text", json={"text": "beholder also runs on a self-hosted vps."})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/projects/{project_id}/extract")
    assert r.status_code == 200, r.text
    r = await client.get(f"/api/projects/{project_id}/model-versions")
    assert r.status_code == 200, r.text
    versions = r.json()
    assert len(versions) >= 2
    assert versions[0]["parent_id"] == versions[1]["id"]  # the chain points backwards
    r = await client.get(f"/api/projects/{project_id}/model-versions/diff")
    assert r.status_code == 200, r.text
    diff = r.json()
    assert set(diff) == {"from_version", "to_version", "facts_added", "facts_removed", "status_changes", "sources_added", "sources_removed"}
    assert versions[0]["id"] in diff["to_version"]


async def test_projects_of_others_do_not_exist_to_you(client):
    r = await client.post("/api/projects", json={"name": "mine"})
    project_id = r.json()["id"]
    # a second caller with a different dev identity
    other = {"headers": {"authorization": "bearer someone-else"}}
    r = await client.get("/api/projects/demo-not-real/facts", headers=other["headers"])
    assert r.status_code == 404  # cannot see what is not yours
    r = await client.get(f"/api/projects/{project_id}/facts", headers=other["headers"])
    assert r.status_code == 404  # a real project of someone else is the same 404

    # the per-id routes resolve the project before acting: a stranger cannot
    # score, pitch, read gaps, or export what is not theirs. it is a 404,
    # not a 403: what they cannot see does not exist to them.
    r = await client.post(f"/api/projects/{project_id}/sources/text", json={"text": "a tool that scores projects."})
    await client.post(f"/api/projects/{project_id}/extract")
    preset = (await client.get("/api/presets")).json()
    r = await client.post(
        f"/api/projects/{project_id}/targets/from-preset",
        json={"preset_key": preset[0]["key"], "label": "hackathon"},
    )
    assert r.status_code == 200, r.text
    target_id = r.json()["target_id"]
    for path in [f"/api/targets/{target_id}/gaps"]:
        r = await client.get(path, headers=other["headers"])
        assert r.status_code == 404
    for path in [f"/api/targets/{target_id}/score", f"/api/targets/{target_id}/pitch", f"/api/targets/{target_id}/check-claims"]:
        r = await client.post(path, json={"pitch_text": "x"} if "check-claims" in path else None, headers=other["headers"])
        assert r.status_code == 404, (path, r.status_code)
    r = await client.post(f"/api/projects/{project_id}/sources/repo", json={"repo_url": "https://github.com/o/r"})
    job_id = r.json()["job_id"]
    r = await client.get(f"/api/jobs/{job_id}", headers=other["headers"])
    assert r.status_code == 404
