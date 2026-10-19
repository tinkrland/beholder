"""the gateway. the only module that talks to any model.

task ids are the contract: extract_facts, parse_rubric, draft_lens,
score_criterion, check_claims, generate_view, bind_sentences. the gateway owns
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
    out_schema: type[BaseModel] | None = None
    temperature: float = 0.2


TASKS: dict[str, TaskSpec] = {
    "extract_facts": TaskSpec(
        task_id="extract_facts",
        prompt_version="1",
        system=(
            "you extract facts from project sources. every fact must be supported by "
            "the text you were given. never invent details. each fact carries the "
            "source ref and the lines it came from. kinds: capability, audience, "
            "pricing, platform, mechanic, maturity, differentiator, alternative, "
            "constraint, metric."
        ),
        user_template="source: {ref}\nlines {lines_start}-{lines_end}\n\n{text}",
    ),
    "parse_rubric": TaskSpec(
        task_id="parse_rubric",
        prompt_version="1",
        system=(
            "you parse judging rubrics and calls for proposals. extract criteria, "
            "weights, required questions, required artifacts, stated priorities, "
            "impresses, and red flags. if a weight is stated in the source, use it "
            "exactly. if any weight is not stated, propose equal weights and set "
            "inferred_weight to true for those criteria. never guess a stated weight: "
            "wrong weights silently skew every score."
        ),
        user_template="rubric source: {source}\n\n{text}",
    ),
    "draft_lens": TaskSpec(
        task_id="draft_lens",
        prompt_version="1",
        system=(
            "you draft a lens from a plain-language description of a reader. criteria "
            "come from the description; equal weights, all marked inferred_weight true. "
            "mark which fields you drafted rather than read: they need review before "
            "the first render."
        ),
        user_template="reader description: {description}",
    ),
    "score_criterion": TaskSpec(
        task_id="score_criterion",
        prompt_version="1",
        system=(
            "you score one criterion of a lens against project facts. score 0 to 5. "
            "a fact from a more-trusted evidence kind counts for more. if no fact "
            "supports the criterion, score 0 and say what evidence would raise it in "
            "raise_by. for subjective criteria return a range as well as a point "
            "estimate. your reasoning names the facts you used, by id. scores are "
            "advisory judgments, not measurements: never present them otherwise."
        ),
        user_template="criterion: {criterion}\nlens strong answer: {strong_answer}\n\nfacts:\n{facts}",
        temperature=0.0,
    ),
    "check_claims": TaskSpec(
        task_id="check_claims",
        prompt_version="1",
        system=(
            "you check one atomic claim from a user's pitch against project facts. "
            "verdict: supported, partial, unsupported, or contradicted. name the fact "
            "ids you rest on. for any verdict other than supported, write a "
            "suggested_rewrite that the facts do support. never invent evidence to "
            "close the gap."
        ),
        user_template="claim: {claim}\n\nfacts:\n{facts}",
        temperature=0.0,
    ),
    "generate_view": TaskSpec(
        task_id="generate_view",
        prompt_version="1",
        system=(
            "you write one section of a pitch view for one reader. use only the facts "
            "provided and the lens framing. every sentence must rest on at least one "
            "fact about the project or on a lens criterion. keep the lens's own "
            "vocabulary. positioning, never marketing: no invented traction, no "
            "metrics that are not in the facts."
        ),
        user_template="section: {section_key}\nlens framing:\n{lens}\n\nfacts:\n{facts}",
    ),
    "bind_sentences": TaskSpec(
        task_id="bind_sentences",
        prompt_version="1",
        system=(
            "you bind sentences to facts. for each sentence, list the fact ids it "
            "rests on, or the lens criteria it talks about (about the audience, not "
            "the project). a sentence resting on nothing is unbound: say so, do not "
            "rescue it."
        ),
        user_template="lens criteria: {criteria}\n\nfacts:\n{facts}\n\nsentences:\n{sentences}",
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
                {"role": "system", "content": spec.system},
                {"role": "user", "content": user_content},
            ],
            "temperature": spec.temperature,
        }
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
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
        raise RuntimeError(f"gateway provider failed after retries: {last_error}")


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


def extract_json(content: str) -> Any:
    """model output is expected to be json. tolerate code fences."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return json.loads(text)
