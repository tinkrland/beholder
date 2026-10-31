"""pydantic shapes, mirroring build-spec section 5. these are the wire format
between the api, the brain, and the gateway."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FactKind = Literal[
    "capability",
    "audience",
    "pricing",
    "platform",
    "mechanic",
    "maturity",
    "differentiator",
    "alternative",
    "constraint",
    "metric",
    "plan",
]

FactStatus = Literal["inferred", "confirmed", "rejected"]
LensType = Literal["rubric", "preset", "custom"]
Verdict = Literal["supported", "partial", "unsupported", "contradicted"]


class Provenance(BaseModel):
    type: Literal["file", "doc", "url", "user"]
    ref: str  # repo/path, doc id, url, or "user"
    lines: list[int] | None = None  # [start, end]
    page: int | None = None
    commit_sha: str | None = None
    forge: str | None = None
    repo_id: str | None = None


class FactIn(BaseModel):
    project_id: str
    kind: FactKind
    statement: str
    value: dict[str, Any] | None = None
    provenance: list[Provenance]
    confidence: float = 0.5
    status: FactStatus = "inferred"
    # observed: read from something that exists. claimed: read from a spec
    # describing something not built yet.
    basis: str = "observed"


class FactOut(FactIn):
    id: str
    content_hash: str
    user_stated: bool = False

    def is_user_stated(self) -> bool:
        return all(p.type == "user" for p in self.provenance)


class Criterion(BaseModel):
    name: str
    weight: float
    description: str | None = None
    strong_answer: str | None = None
    subjective: bool = False
    inferred_weight: bool = False  # true when the weight was proposed, not stated


class LensDraft(BaseModel):
    """output of the lens builder before review. review_status is draft."""

    type: LensType
    name: str
    criteria: list[Criterion]
    required_questions: list[str] = []
    required_artifacts: list[str] = []
    impresses: list[str] = []
    red_flags: list[str] = []
    alternatives_frame: str | None = None
    trusted_evidence: list[str] = []
    objection_seeds: list[str] = []
    vocabulary: list[str] = []
    output_formats: list[str] = []
    sources: list[dict[str, str]] = []
    inferred_fields: list[str] = []  # which fields were drafted, not stated
    last_verified: date | None = None


class LensOut(LensDraft):
    id: str
    owner_id: str | None = None
    version: int = 1
    staleness_days: int | None = None
    visibility: Literal["private", "shared"] = "private"
    review_status: Literal["draft", "confirmed"] = "draft"
    created_at: datetime | None = None

    def is_stale(self, today: date | None = None) -> bool:
        if self.staleness_days is None or self.last_verified is None:
            return False
        today = today or date.today()
        return (today - self.last_verified).days > self.staleness_days


class CriterionScore(BaseModel):
    criterion: str
    score: float  # 0..5
    range: list[float] | None = None  # [lo, hi] for subjective criteria
    reasoning: str
    fact_ids: list[str] = []
    raise_by: str | None = None


class ScoreOut(BaseModel):
    id: str
    target_id: str
    model_version_id: str
    per_criterion: list[CriterionScore]
    weighted_total: float
    confidence: float


class GapOut(BaseModel):
    id: str
    target_id: str
    criterion: str
    weight: float
    missing: str
    would_close: str


class ClaimCheckOut(BaseModel):
    id: str
    target_id: str
    claim_text: str
    verdict: Verdict
    fact_ids: list[str] = []
    suggested_rewrite: str | None = None


class ConsistencySide(BaseModel):
    target_id: str
    label: str
    sentence: str


class ConsistencyContradiction(BaseModel):
    a: ConsistencySide
    b: ConsistencySide
    explanation: str | None = None


class ConsistencyCheckedView(BaseModel):
    target_id: str
    label: str
    sentence_count: int


class ConsistencyReportOut(BaseModel):
    checked_views: list[ConsistencyCheckedView] = []
    pairs_checked: int = 0
    echoes: int = 0
    contradictions: list[ConsistencyContradiction] = []
    consistent: bool = True
    note: str | None = None


class Sentence(BaseModel):
    id: str
    text: str
    fact_ids: list[str] = []
    criterion_ids: list[str] = []
    needs_confirmation: bool = False  # bound to an unconfirmed, low-confidence fact


SECTION_KEYS = [
    "one_liner",
    "category_frame",
    "problem_as_they_see_it",
    "alternatives",
    "what_is_different",
    "proof",
    "objections_and_honest_answers",
    "what_not_to_lead_with",
    "gaps",
]


class Section(BaseModel):
    key: str
    sentence_ids: list[str] = []


class PitchViewOut(BaseModel):
    id: str
    target_id: str
    model_version_id: str
    lens_version: int
    sections: list[Section]
    sentences: list[Sentence]
    annotations: list[dict] = []
    stale: bool = False
    cache_key: str


class HonestyReport(BaseModel):
    exportable: bool
    unbound_sentence_ids: list[str] = []
    needs_confirmation_fact_ids: list[str] = []
    blocking: list[str] = []  # human-readable reasons export is blocked
