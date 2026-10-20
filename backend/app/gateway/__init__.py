"""the gateway. the only module that talks to any model.

task ids are the contract: extract_facts, parse_rubric, draft_lens,
score_criterion, check_claims, generate_view, bind_sentences,
check_consistency. the gateway owns
prompt versions, response schemas, caching, retries, and cost metering. a
fine-tuned model can slot in behind the same interface later with no caller
changes: the brain passes task ids, never provider names.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from ..config import settings


@dataclass
class TaskSpec:
    task_id: str
    prompt_version: str
    system: str
    user_template: str
    out_format: str = ""
    temperature: float = 0.2


TASKS: dict[str, TaskSpec] = {
    "extract_facts": TaskSpec(
        task_id="extract_facts",
        prompt_version="3",
        system=(
            "you extract facts from project sources. every fact must be supported by "
            "the text you were given. never invent details. each fact carries the "
            "source ref and the lines it came from. kinds: capability, audience, "
            "pricing, platform, mechanic, maturity, differentiator, alternative, "
            "constraint, metric."
        ),
        user_template="source: {ref}\nlines {lines_start}-{lines_end}\n\n{text}",
        out_format='{"facts": [{"kind": "capability|audience|pricing|platform|mechanic|maturity|differentiator|alternative|constraint|metric", "statement": "one thing the text supports", "value": {"value": "0.1.0", "unit": "optional"} or null, "lines": [start_line, end_line]}]}',
    ),
    "parse_rubric": TaskSpec(
        task_id="parse_rubric",
        prompt_version="2",
        system=(
            "you parse judging rubrics and calls for proposals. extract criteria, "
            "weights, required questions, required artifacts, stated priorities, "
            "impresses, and red flags. if a weight is stated in the source, use it "
            "exactly. if any weight is not stated, propose equal weights and set "
            "inferred_weight to true for those criteria. never guess a stated weight: "
            "wrong weights silently skew every score."
        ),
        user_template="rubric source: {source}\n\n{text}",
        out_format='{"name": "rubric name", "criteria": [{"name": "criterion", "weight": 0.3, "description": "what strong looks like", "strong_answer": "optional", "subjective": false, "inferred_weight": false}], "required_questions": ["question"], "required_artifacts": ["artifact"], "impresses": ["what impresses this reader"], "red_flags": ["what this reader distrusts"], "trusted_evidence": ["evidence kinds this reader trusts"]}',
    ),
    "draft_lens": TaskSpec(
        task_id="draft_lens",
        prompt_version="2",
        system=(
            "you draft a lens from a plain-language description of a reader. criteria "
            "come from the description; equal weights, all marked inferred_weight true. "
            "mark which fields you drafted rather than read: they need review before "
            "the first render."
        ),
        user_template="reader description: {description}",
        out_format='{"name": "lens name", "criteria": [{"name": "criterion", "description": "what strong looks like"}], "impresses": ["what impresses this reader"]}',
    ),
    "score_criterion": TaskSpec(
        task_id="score_criterion",
        prompt_version="2",
        system=(
            "you score one criterion of a lens against project facts. score 0 to 5. "
            "a fact from a more-trusted evidence kind counts for more. if no fact "
            "supports the criterion, score 0 and say what evidence would raise it in "
            "raise_by. for subjective criteria return a range as well as a point "
            "estimate. your reasoning names the facts you used, by id. scores are "
            "advisory judgments, not measurements: never present them otherwise."
        ),
        user_template="criterion: {criterion}\nlens strong answer: {strong_answer}\n\nfacts:\n{facts}",
        out_format='{"score": 0.0, "range": [0.0, 1.0], "reasoning": "which fact ids and why", "fact_ids": ["id"], "raise_by": "what evidence would raise the score"}',
        temperature=0.0,
    ),
    "check_claims": TaskSpec(
        task_id="check_claims",
        prompt_version="2",
        system=(
            "you check one atomic claim from a user's pitch against project facts. "
            "verdict: supported, partial, unsupported, or contradicted. name the fact "
            "ids you rest on. for any verdict other than supported, write a "
            "suggested_rewrite that the facts do support. never invent evidence to "
            "close the gap."
        ),
        user_template="claim: {claim}\n\nfacts:\n{facts}",
        out_format='{"verdict": "supported|partial|unsupported|contradicted", "fact_ids": ["id"], "suggested_rewrite": "only for verdicts other than supported"}',
        temperature=0.0,
    ),
    "generate_view": TaskSpec(
        task_id="generate_view",
        prompt_version="2",
        system=(
            "you write one section of a pitch view for one reader. use only the facts "
            "provided and the lens framing. every sentence must rest on at least one "
            "fact about the project or on a lens criterion. keep the lens's own "
            "vocabulary. positioning, never marketing: no invented traction, no "
            "metrics that are not in the facts."
        ),
        user_template="section: {section_key}\nlens framing:\n{lens}\n\nfacts:\n{facts}",
        out_format='{"sentences": ["sentence one.", "sentence two."]}',
    ),
    "check_consistency": TaskSpec(
        task_id="check_consistency",
        prompt_version="2",
        system=(
            "you compare sentences that one project says to two different readers. "
            "two sentences contradict when they cannot both be true of the same "
            "project: different scopes for the same claim, different numbers for the "
            "same thing, one view promising what another view says is not built. "
            "framing differences are not contradictions: each reader sees a different "
            "emphasis of one truth. verdicts are consistent, contradiction, or "
            "unrelated. never invent a contradiction: when unsure, unrelated."
        ),
        user_template="views:\n{views}\n\npairs:\n{pairs}",
        out_format='{"verdicts": [{"verdict": "consistent|contradiction|unrelated", "explanation": "required for contradiction: why both cannot be true"}]}',
    ),
    "bind_sentences": TaskSpec(
        task_id="bind_sentences",
        prompt_version="2",
        system=(
            "you bind sentences to facts. for each sentence, list the fact ids it "
            "rests on, or the lens criteria it talks about (about the audience, not "
            "the project). a sentence resting on nothing is unbound: say so, do not "
            "rescue it."
        ),
        user_template="lens criteria: {criteria}\n\nfacts:\n{facts}\n\nsentences:\n{sentences}",
        out_format='{"bindings": [{"index": 0, "fact_ids": ["id"], "criterion_ids": ["criterion name"]}]}',
        temperature=0.0,
    ),
}


def cache_key(task_id: str, payload: dict[str, Any]) -> str:
    """hash(task + sorted payload + prompt version). cache key per build-spec 5."""
    spec = TASKS[task_id]
    blob = json.dumps({"task": task_id, "v": spec.prompt_version, "payload": payload}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class Provider(Protocol):
    async def complete(self, spec: TaskSpec, user_content: str) -> dict[str, Any]: ...


class GlmProvider:
    """glm through its openai-compatible endpoint. keys come from the environment."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.glm_api_key
        self.base_url = base_url or settings.glm_base_url
        self.model = model or settings.glm_model

    async def complete(self, spec: TaskSpec, user_content: str) -> dict[str, Any]:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": effective_system(spec)},
                {"role": "user", "content": user_content},
            ],
            "temperature": spec.temperature,
        }
        last_error: Exception | None = None
        # a thinking model on a big composite payload (pitch, consistency)
        # regularly runs past two minutes. the socket must outlive it.
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=600) as client:
                    r = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=body,
                        headers={"authorization": f"bearer {self.api_key}"},
                    )
                    r.raise_for_status()
                    data = r.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "content": text,
                    "in_tokens": usage.get("prompt_tokens", 0),
                    "out_tokens": usage.get("completion_tokens", 0),
                    "model": self.model,
                }
            except Exception as e:  # noqa: ble001 - retries then raises
                last_error = e
        raise RuntimeError(f"gateway provider failed after retries: {last_error!r}")


@dataclass
class MockProvider:
    """canned responses for tests and local runs without keys. the provider is
    constructed with a callable that receives (spec, user_content) and returns
    the same dict shape the glm provider returns."""

    responder: Any = None
    calls: list = field(default_factory=list)

    async def complete(self, spec: TaskSpec, user_content: str) -> dict[str, Any]:
        self.calls.append((spec.task_id, user_content))
        if self.responder is None:
            raise RuntimeError(f"mock provider has no canned response for {spec.task_id}")
        out = self.responder(spec, user_content)
        if isinstance(out, dict) and "content" not in out:
            out = {"content": out if isinstance(out, str) else json.dumps(out), "in_tokens": 1, "out_tokens": 1, "model": "mock"}
        return out


def effective_system(spec: TaskSpec) -> str:
    """judgment lives in the prompt; the machine contract is appended here so
    every provider sends the same wire format. without it a real model
    free-forms and json parsing dies."""
    if not spec.out_format:
        return spec.system
    return (
        f"{spec.system}\n\n"
        "respond with only json, no prose before or after, in exactly this shape:\n"
        f"{spec.out_format}"
    )


def extract_json(content: str) -> Any:
    """model output is expected to be json. tolerate code fences."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return json.loads(text)
