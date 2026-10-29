"""orm tables, one per structure in build-spec section 5, plus jobs and gateway calls.

rules that live here:
- model_version, score, pitch_view, export are immutable: insert-only. the
  code never issues an update against them.
- provenance is jsonb with the shapes from build-spec 4.
- source carries kind: repo | doc | url | text, and forge.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, Json


def uid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def json_type():
    """jsonb on postgres, json elsewhere."""
    return Json().with_variant(postgresql.JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(Text, unique=True)
    auth_id: Mapped[str] = mapped_column(Text, unique=True)  # supabase user id
    plan: Mapped[str] = mapped_column(Text, default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectMember(Base):
    """owner_id sits behind a membership table so teams can be added without migration."""

    __tablename__ = "project_members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(Text, default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(Text)  # repo | doc | url | text
    forge: Mapped[str | None] = mapped_column(Text)  # github | gitlab | bitbucket | gitea
    ref: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    commit_sha: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    idx: Mapped[int] = mapped_column(default=0)
    path: Mapped[str | None] = mapped_column(Text)
    lines_start: Mapped[int | None] = mapped_column(default=0)
    lines_end: Mapped[int | None] = mapped_column(default=0)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, default="file")  # file | doc | url | user
    page: Mapped[int | None] = mapped_column(default=None)  # pdf and docx chunks cite their page
    redacted: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_chunks_source", "source_id", "idx"),)


class Fact(Base):
    __tablename__ = "facts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    value: Mapped[dict | None] = mapped_column(json_type(), default=None)
    provenance: Mapped[list] = mapped_column(json_type(), default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(Text, default="inferred")  # inferred | confirmed | rejected
    content_hash: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_fact_project_kind_status", "project_id", "kind", "status"),)


class ModelVersion(Base):
    """immutable snapshot of the fact set. insert-only."""

    __tablename__ = "model_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    parent_id: Mapped[str | None] = mapped_column(String(36))
    fact_ids: Mapped[list] = mapped_column(json_type(), default=list)
    source_hashes: Mapped[list] = mapped_column(json_type(), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lens(Base):
    __tablename__ = "lenses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str | None] = mapped_column(String(36))
    type: Mapped[str] = mapped_column(Text)  # rubric | preset | custom
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
    criteria: Mapped[list] = mapped_column(json_type(), default=list)
    required_questions: Mapped[list] = mapped_column(json_type(), default=list)
    required_artifacts: Mapped[list] = mapped_column(json_type(), default=list)
    impresses: Mapped[list] = mapped_column(json_type(), default=list)
    red_flags: Mapped[list] = mapped_column(json_type(), default=list)
    alternatives_frame: Mapped[str | None] = mapped_column(Text)
    trusted_evidence: Mapped[list] = mapped_column(json_type(), default=list)
    objection_seeds: Mapped[list] = mapped_column(json_type(), default=list)
    vocabulary: Mapped[list] = mapped_column(json_type(), default=list)
    output_formats: Mapped[list] = mapped_column(json_type(), default=list)
    sources: Mapped[list] = mapped_column(json_type(), default=list)
    last_verified: Mapped[date | None] = mapped_column(Date)
    staleness_days: Mapped[int | None] = mapped_column(default=None)
    visibility: Mapped[str] = mapped_column(Text, default="private")
    inferred_fields: Mapped[list] = mapped_column(json_type(), default=list)  # fields drafted, not stated
    # the mandatory review step: draft lenses never score. confirmed means a
    # human has confirmed or edited the parse, including every inferred weight.
    review_status: Mapped[str] = mapped_column(Text, default="draft")
    # the shared library: None never contributed, submitted waits for a
    # reviewer, approved is public, rejected stays private.
    library_status: Mapped[str | None] = mapped_column(Text, default=None)
    contributed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Target(Base):
    __tablename__ = "targets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    lens_id: Mapped[str] = mapped_column(ForeignKey("lenses.id"))
    lens_version: Mapped[int] = mapped_column(default=1)
    label: Mapped[str] = mapped_column(Text)
    deadline: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Score(Base):
    """immutable. insert-only, latest found by ordering, never an update."""

    __tablename__ = "scores"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id"))
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"))
    per_criterion: Mapped[list] = mapped_column(json_type(), default=list)
    weighted_total: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_score_target", "target_id", "created_at"),)


class Gap(Base):
    __tablename__ = "gaps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id"))
    criterion: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float)
    missing: Mapped[str] = mapped_column(Text)
    would_close: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClaimCheck(Base):
    __tablename__ = "claim_checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id"))
    claim_text: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(Text)  # supported | partial | unsupported | contradicted
    fact_ids: Mapped[list] = mapped_column(json_type(), default=list)
    suggested_rewrite: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PitchView(Base):
    """immutable. annotations carry pinned fact hashes, never silent drops."""

    __tablename__ = "pitch_views"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id"))
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"))
    lens_version: Mapped[int] = mapped_column(default=1)
    sections: Mapped[list] = mapped_column(json_type(), default=list)
    sentences: Mapped[list] = mapped_column(json_type(), default=list)
    annotations: Mapped[list] = mapped_column(json_type(), default=list)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_view_target_model", "target_id", "model_version_id"),)


class Export(Base):
    """immutable. export is blocked on honesty failures, so this only exists
    after the guard passes or the user confirmed every flagged fact."""

    __tablename__ = "exports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    view_id: Mapped[str] = mapped_column(ForeignKey("pitch_views.id"))
    format_id: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    confirmed_unsupported: Mapped[list] = mapped_column(json_type(), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ForgeAccount(Base):
    """a connected forge account: one per user and forge. tokens are read-only
    repo credentials; stored server-side, never echoed back whole."""

    __tablename__ = "forge_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36))
    forge: Mapped[str] = mapped_column(Text)  # github | gitlab | bitbucket | gitea
    token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str | None] = mapped_column(String(36))
    user_id: Mapped[str | None] = mapped_column(String(36))  # who enqueued: token resolution needs it
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending | running | done | failed
    payload: Mapped[dict] = mapped_column(json_type(), default=dict)
    progress: Mapped[dict] = mapped_column(json_type(), default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GatewayCall(Base):
    """cost metering and cache log. one row per real model call, cached hits logged too.
    result holds the parsed output so the same cache key never pays twice."""

    __tablename__ = "gateway_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(Text)
    cache_key: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(json_type(), default=dict)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_version: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    in_tokens: Mapped[int] = mapped_column(default=0)
    out_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
