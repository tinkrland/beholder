"""unit tests for the brain: retrieval, scorer, claims, honesty, lens builder,
projector, extraction. no api, no db, no network: every model call is canned."""

import pytest

from app.brain import claims, extraction, honesty, lens_builder, projector, scorer
from app.schemas import Criterion, FactOut, LensOut, PitchViewOut, Provenance, Section, Sentence
from conftest import FakeRun


def fact(fid="f1", statement="the project renders the exact product mesh", conf=0.8, status="inferred", kind="capability", prov_type="file"):
    return FactOut(
        id=fid,
        project_id="p1",
        kind=kind,
        statement=statement,
        provenance=[Provenance(type=prov_type, ref="readme.md", lines=[1, 4])],
        confidence=conf,
        status=status,
        content_hash="h" + fid,
    )


def lens(criteria=None, confirmed=True):
    return LensOut(
        id="l1",
        type="rubric",
        name="test lens",
        version=1,
        criteria=criteria or [Criterion(name="technical depth", weight=0.5, description="non-trivial engineering"), Criterion(name="demo quality", weight=0.5, description="a working demo")],
        trusted_evidence=["public repo with recent commits"],
        review_status="confirmed" if confirmed else "draft",
    )


# ---------- retrieval ----------

def test_relevant_facts_rank_by_overlap_and_trust():
    f1 = fact("f1", "the deterministic engine rebuilds geometry")
    f2 = fact("f2", "the deterministic engine rebuilds geometry", prov_type="user")
    picked = __import__("app.brain.retrieval", fromlist=["relevant_facts"]).relevant_facts("deterministic engine rebuilds geometry", [f2, f1], lens())
    assert picked[0].id == "f1"  # file evidence outranks user-stated


def test_rejected_facts_never_appear():
    f = fact("f1", "the deterministic engine rebuilds geometry", status="rejected")
    assert not [x for x in __import__("app.brain.retrieval", fromlist=["relevant_facts"]).relevant_facts("deterministic engine", [f], lens()) if x.status == "rejected"]


# ---------- scorer ----------

async def test_score_target_gaps_and_weighted_total():
    run = FakeRun(
        {
            "score_criterion": lambda p: (
                {"score": 4, "reasoning": "strong", "fact_ids": ["f1"], "raise_by": "benchmarks"}
                if p["criterion"] == "technical depth"
                else {"score": 0, "reasoning": "nothing", "fact_ids": [], "raise_by": "a demo video"}
            )
        }
    )
    score, gaps = await scorer.score_target("t1", "mv1", [fact()], lens(), run)
    assert score.weighted_total == pytest.approx(2.0)  # 0.5*4 + 0.5*0
    assert len(gaps) == 1 and gaps[0].criterion == "demo quality"
    assert gaps[0].would_close == "a demo video"


async def test_subjective_criteria_return_ranges():
    run = FakeRun({"score_criterion": lambda p: {"score": 3, "reasoning": "fresh", "fact_ids": ["f1"], "range": [2, 4]}})
    crit = Criterion(name="originality", weight=1.0, subjective=True)
    score, _ = await scorer.score_target("t1", "mv1", [fact()], lens(criteria=[crit]), run)
    assert score.per_criterion[0].range == [2.0, 4.0]


async def test_fact_ids_not_in_prompt_are_dropped():
    run = FakeRun({"score_criterion": lambda p: {"score": 5, "reasoning": "no", "fact_ids": ["not-a-real-fact"], "fact_ids_ok": None}})
    score, _ = await scorer.score_target("t1", "mv1", [fact()], lens(), run)
    assert score.per_criterion[0].fact_ids == []


# ---------- claims ----------

def test_atomic_claims_split():
    text = "we built an engine. it renders fast, and it never hallucinates. but scale is untested."
    got = claims.atomic_claims(text)
    assert len(got) >= 3
    assert all(len(c) > 3 for c in got)


async def test_check_claims_verdicts_and_rewrites():
    run = FakeRun({"check_claims": lambda p: {"verdict": "unsupported", "fact_ids": [], "suggested_rewrite": "the project renders deterministic geometry"}})
    out = await claims.check_claims("the engine never cracks.", [fact()], run)
    assert out[0].verdict == "unsupported"
    assert out[0].suggested_rewrite.startswith("the project renders")


async def test_unknown_verdict_is_not_trusted():
    run = FakeRun({"check_claims": lambda p: {"verdict": "definitely-true", "fact_ids": [], "suggested_rewrite": None}})
    out = await claims.check_claims("the engine never cracks.", [fact()], run)
    assert out[0].verdict == "unsupported"  # anything outside the four is unsupported


# ---------- honesty guard ----------

def bound_view(conf=0.6, status="inferred"):
    f = fact("f1", conf=conf, status=status)
    view = PitchViewOut(
        id="v1",
        target_id="t1",
        model_version_id="mv1",
        lens_version=1,
        sections=[Section(key="proof", sentence_ids=["s1"])],
        sentences=[Sentence(id="s1", text="the engine is deterministic.", fact_ids=["f1"])],
        cache_key="k",
    )
    return view, {"f1": f}


def test_export_blocked_on_unconfirmed_low_confidence_fact():
    view, facts = bound_view(conf=0.5, status="inferred")
    report = honesty.validate_view(view, facts)
    assert not report.exportable
    assert report.needs_confirmation_fact_ids == ["f1"]


def test_export_allowed_when_fact_confirmed():
    view, facts = bound_view(conf=0.5, status="confirmed")
    assert honesty.validate_view(view, facts).exportable


def test_export_confirmation_lifts_block():
    view, facts = bound_view(conf=0.5, status="inferred")
    report = honesty.can_export(view, facts, ["f1"])
    assert report.exportable


def test_unbound_sentences_block():
    view = PitchViewOut(
        id="v1", target_id="t1", model_version_id="mv1", lens_version=1,
        sections=[Section(key="proof", sentence_ids=["s1"])],
        sentences=[Sentence(id="s1", text="we are the best.")],
        cache_key="k",
    )
    report = honesty.validate_view(view, {})
    assert not report.exportable and report.unbound_sentence_ids == ["s1"]


# ---------- lens builder ----------

async def test_unstated_weights_become_inferred_and_equal():
    run = FakeRun(
        {
            "parse_rubric": {
                "name": "vague rubric",
                "criteria": [{"name": "quality"}, {"name": "impact"}, {"name": "vibe", "subjective": True}],
            }
        }
    )
    draft = await lens_builder.parse_rubric("some rubric text", "rubric.pdf", run)
    assert all(c.inferred_weight for c in draft.criteria)
    assert sum(c.weight for c in draft.criteria) == pytest.approx(1.0, abs=1e-3)
    assert draft.type == "rubric" and draft.criteria  # a draft, ready for review


async def test_stated_weights_pass_through_unmarked():
    run = FakeRun(
        {
            "parse_rubric": {
                "name": "weighted rubric",
                "criteria": [{"name": "tech", "weight": 0.6}, {"name": "impact", "weight": 0.4}],
            }
        }
    )
    draft = await lens_builder.parse_rubric("text", "sheet.pdf", run)
    assert all(not c.inferred_weight for c in draft.criteria)
    assert draft.criteria[0].weight == pytest.approx(0.6)


def test_confirm_lens_requires_criteria():
    l = lens(confirmed=False)
    l.criteria = []
    with pytest.raises(ValueError):
        lens_builder.confirm_lens(l)


def test_confirm_lens_flips_status():
    l = lens(confirmed=False)
    lens_builder.confirm_lens(l)
    assert l.review_status == "confirmed"


# ---------- projector ----------

async def test_projector_drops_unbound_and_binds_rest():
    f = fact("f1")
    run = FakeRun(
        {
            "generate_view": {"sentences": ["bound sentence one.", "unbound fluff."]},
            "bind_sentences": {
                "bindings": [
                    {"index": 0, "fact_ids": ["f1"], "criterion_ids": []},
                    {"index": 1, "fact_ids": [], "criterion_ids": []},
                ]
            },
        }
    )
    view = await projector.project("t1", "mv1", [f], lens(), run)
    texts = [s.text for s in view.sentences]
    assert "unbound fluff." not in texts
    assert texts == ["bound sentence one."]
    assert view.sentences[0].fact_ids == ["f1"]
    dropped = [a for a in view.annotations if a.get("type") == "dropped"]
    assert dropped and dropped[0]["items"][0]["text"] == "unbound fluff."


async def test_projector_has_nine_sections():
    run = FakeRun(
        {
            "generate_view": {"sentences": ["a bound sentence."]},
            "bind_sentences": {"bindings": [{"index": i, "fact_ids": ["f1"], "criterion_ids": []} for i in range(40)]},
        }
    )
    view = await projector.project("t1", "mv1", [fact()], lens(), run)
    assert len(view.sections) == 9
    assert [s.key for s in view.sections] == [
        "one_liner", "category_frame", "problem_as_they_see_it", "alternatives",
        "what_is_different", "proof", "objections_and_honest_answers",
        "what_not_to_lead_with", "gaps",
    ]


# ---------- extraction ----------

def test_static_pass_reads_package_json():
    chunks = [{"path": "package.json", "text": '{"name": "studiogram", "dependencies": {"three": "^0.160.0"}}', "lines_start": 1, "lines_end": 1}]
    facts = extraction.static_pass(chunks)
    kinds = {f.kind for f in facts}
    assert "capability" in kinds and "platform" in kinds and "constraint" in kinds
    assert any("three" in f.statement for f in facts)


def test_static_pass_ignores_broken_json():
    assert extraction.static_pass([{"path": "package.json", "text": "{broken", "lines_start": 1, "lines_end": 1}]) == []


def test_structural_pass_reads_repo_shape():
    facts = extraction.structural_pass(["src/api/routes.py", "src/tests/test_x.py", "docs/guide.md"])
    statements = " ".join(f.statement for f in facts)
    assert "api surface" in statements
    assert "tests exist" in statements


def test_structural_pass_is_observed_not_verified():
    facts = extraction.structural_pass(["src/api/routes.py"])
    assert facts[0].confidence < 0.7  # file evidence only claims so much


async def test_semantic_pass_provenance_comes_from_chunk():
    run = FakeRun({"extract_facts": {"facts": [{"kind": "capability", "statement": "the project renders deterministic geometry", "lines": [3, 12]}]}})
    facts = await extraction.semantic_pass([{"path": "readme.md", "text": "text", "lines_start": 1, "lines_end": 40, "commit_sha": "sha123"}], "p1", run)
    assert facts[0].provenance[0].ref == "readme.md"
    assert facts[0].provenance[0].lines == [3, 12]
    assert facts[0].provenance[0].commit_sha == "sha123"


def test_every_extraction_fact_has_provenance():
    chunks = [{"path": "requirements.txt", "text": "fastapi\nhttpx", "lines_start": 1, "lines_end": 2}]
    for f in extraction.static_pass(chunks):
        assert f.provenance and f.provenance[0].ref
