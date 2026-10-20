"""gateway tests: caching by cache key, mock provider, json extraction."""

import json

import pytest

from app.gateway import TASKS, MockProvider, cache_key, effective_system, extract_json
from app.gateway.runner import SimpleRunner


async def test_same_payload_hits_cache_once(db_session):
    provider = MockProvider(responder=lambda spec, content: {"content": json.dumps({"ok": True}), "in_tokens": 1, "out_tokens": 1, "model": "mock"})
    run = SimpleRunner(db_session, provider)
    payload = {"criterion": "technical depth", "strong_answer": "x", "facts": "[f1] a fact"}
    first = await run("score_criterion", payload)
    second = await run("score_criterion", payload)
    assert first == second == {"ok": True}
    assert len(provider.calls) == 1  # the second call was a cache hit


async def test_different_payload_is_a_new_call(db_session):
    provider = MockProvider(responder=lambda spec, content: {"content": "{}", "in_tokens": 1, "out_tokens": 1, "model": "mock"})
    run = SimpleRunner(db_session, provider)
    await run("score_criterion", {"criterion": "a", "strong_answer": "", "facts": ""})
    await run("score_criterion", {"criterion": "b", "strong_answer": "", "facts": ""})
    assert len(provider.calls) == 2


def test_cache_key_is_deterministic_and_prompt_versioned():
    p = {"x": 1}
    assert cache_key("parse_rubric", p) == cache_key("parse_rubric", {"x": 1})
    assert cache_key("parse_rubric", p) != cache_key("extract_facts", p)


def test_extract_json_tolerates_code_fences():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('{"a": 1}') == {"a": 1}


def test_mock_provider_without_responder_raises():
    import asyncio

    async def go():
        from app.gateway import TASKS

        try:
            await MockProvider().complete(TASKS["parse_rubric"], "x")
            return False
        except RuntimeError:
            return True

    assert asyncio.run(go())


def test_every_task_declares_its_output_contract():
    """a real model free-formats without a stated wire format: every task
    must carry one, and the provider must append it to the system prompt."""
    for task_id, spec in TASKS.items():
        assert spec.out_format, f"{task_id} has no out_format"
        assert "respond with only json" in effective_system(spec)
        assert spec.prompt_version != "1", f"{task_id} prompt version must reflect the contract"
