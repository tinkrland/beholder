"""preset lens tests: authored files load honestly, staleness and drift are
pure arithmetic, sync upserts and version-bumps, refresh verifies only when
sources resolve. no network: refresh runs on a mock transport."""

import json
from datetime import date, timedelta

import httpx

from app.brain.presets import drift_check, is_stale, preset_summary
from app.presets import load_presets, preset_by_key


# ---------- authored files ----------

def test_presets_load_with_honest_shapes():
    presets = load_presets()
    assert len(presets) >= 4
    for p in presets:
        assert p["criteria"], f"{p['key']} has no criteria"
        assert p["sources"] or p["key"] == "casting_partner"  # a sourceless preset is allowed, checkable False
        for c in p["criteria"]:
            assert c["name"] and c["weight"] > 0 and (c.get("strong_answer") or c.get("description"))
            assert c["subjective"] is False and c["inferred_weight"] is False  # authored, stated, never inferred


def test_preset_by_key():
    assert preset_by_key("yc_application")["staleness_days"] == 180
    assert preset_by_key("nope") is None


# ---------- staleness, pure ----------

def test_no_staleness_days_never_stale():
    assert is_stale({"staleness_days": None, "last_verified": None}) is False


def test_stale_on_arrival_when_never_verified():
    assert is_stale({"staleness_days": 90, "last_verified": None}) is True


def test_staleness_threshold():
    lens = {"staleness_days": 90, "last_verified": date(2026, 1, 1)}
    assert is_stale(lens, date(2026, 4, 1)) is False  # 90 days: exactly at the bar, not past it
    assert is_stale(lens, date(2026, 4, 2)) is True
    assert is_stale({**lens, "last_verified": "2026-01-01"}, date(2026, 6, 1)) is True  # iso strings accepted


# ---------- drift, pure ----------

def test_drift_check_reports_missing_keywords():
    preset = {"drift_keywords": ["users", "market"]}
    report = drift_check(preset, ["the page now talks only about users"])
    assert report["checkable"] and report["drifted"]
    assert report["keywords_found"] == ["users"] and report["keywords_missing"] == ["market"]


def test_drift_check_without_keywords_or_sources_is_not_checkable():
    assert drift_check({"drift_keywords": []}, ["text"])["checkable"] is False
    assert drift_check({"drift_keywords": ["a"]}, [])["checkable"] is False


# ---------- sync ----------

async def test_ensure_presets_installs_and_version_bumps(db_session):
    from app.service import ensure_presets, list_presets

    rows = await ensure_presets(db_session)
    keys = {r.name for r in rows}
    assert "yc_application" in keys
    assert all(r.type == "preset" and r.review_status == "confirmed" for r in rows)  # authored, not parsed
    assert all(r.last_verified is None for r in rows)  # never verified: stale on arrival, flagged honestly

    listing = await list_presets(db_session)
    yc = next(p for p in listing if p["key"] == "yc_application")
    assert yc["installed"] and yc["stale"] is True  # never verified yet
    assert yc["criteria_count"] == 5

    # a changed authored file bumps the version in place, same lens id
    from app.presets import preset_by_key as _pbk
    lens_id = yc["lens_id"]
    stored = next(r for r in rows if r.name == "yc_application")
    stored.criteria = stored.criteria + [{"name": "a new authored criterion", "weight": 0.0, "strong_answer": "x"}]
    await db_session.commit()
    rows2 = await ensure_presets(db_session)
    yc2 = next(r for r in rows2 if r.name == "yc_application")
    assert yc2.id == lens_id and yc2.version == yc["version"] + 1


# ---------- refresh ----------

def _refresh_transport(body_by_url: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in body_by_url:
            return httpx.Response(200, text=body_by_url[url], headers={"content-type": "text/html"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_refresh_verifies_when_sources_still_read_the_same(db_session):
    from app.service import ensure_presets, refresh_presets

    await ensure_presets(db_session)
    preset = preset_by_key("yc_application")
    client = httpx.AsyncClient(transport=_refresh_transport({preset["sources"][0]: "team market users prototype, all still here"}))
    async with client:
        report = await refresh_presets(db_session, ["yc_application"], client=client)
    row = report["refreshed"][0]
    assert row["verified"] == str(date.today())
    assert row["drifted"] is False and row["keywords_missing"] == []


async def test_refresh_leaves_drifted_presets_stale(db_session):
    from app.service import ensure_presets, refresh_presets

    await ensure_presets(db_session)
    preset = preset_by_key("yc_application")
    client = httpx.AsyncClient(transport=_refresh_transport({preset["sources"][0]: "the page moved on: nothing about any of it"}))
    async with client:
        report = await refresh_presets(db_session, ["yc_application"], client=client)
    row = report["refreshed"][0]
    assert row["verified"] is None  # honest: the source moved, a human re-reads
    assert row["drifted"] is True and row["keywords_missing"]

    # and the listing shows it stale, not patched
    from app.service import list_presets

    listing = await list_presets(db_session)
    yc = next(p for p in listing if p["key"] == "yc_application")
    assert yc["stale"] is True


async def test_refresh_unreachable_sources_fail_not_patch(db_session):
    from app.service import ensure_presets, refresh_presets

    await ensure_presets(db_session)
    client = httpx.AsyncClient(transport=_refresh_transport({}))  # everything 404s
    async with client:
        report = await refresh_presets(db_session, ["yc_application"], client=client)
    row = report["refreshed"][0]
    assert row["verified"] is None and row["error"]


def test_summary_flags_staleness_from_the_installed_row():
    today = date.today()
    preset = preset_by_key("hackathon_demo_judge")
    fresh = preset_summary(preset, {"id": "l1", "version": 2, "last_verified": today - timedelta(days=10)})
    assert fresh["stale"] is False and fresh["installed"] and fresh["version"] == 2
    old = preset_summary(preset, {"id": "l1", "version": 2, "last_verified": today - timedelta(days=400)})
    assert old["stale"] is True
