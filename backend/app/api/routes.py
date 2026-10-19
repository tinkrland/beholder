"""api routes. thin: validate, call the service, return. the api is the source
of truth: the client validates for feel, the api validates for real."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user, require_project_access
from ..db import get_session
from ..gateway.runner import SimpleRunner
from ..models import ClaimCheck, Gap, Job, Lens, Score, Target
from ..service import (
    add_doc_source,
    add_text_source,
    add_url_source,
    grounding_for_project,
    check_claims_rows,
    confirm_lens_row,
    create_project,
    create_target,
    enqueue_job,
    extract_facts,
    generate_view_row,
    list_facts,
    save_lens_draft,
    score_target_rows,
    sync_repo_source,
)

router = APIRouter()


def runner(session: AsyncSession) -> SimpleRunner:
    return SimpleRunner(session)


class ProjectIn(BaseModel):
    name: str


class TextSourceIn(BaseModel):
    text: str
    label: str = "pasted text"


class DocSourceIn(BaseModel):
    filename: str
    text: str | None = None
    content_b64: str | None = None


class UrlSourceIn(BaseModel):
    url: str


class DocsiteIn(BaseModel):
    root_url: str
    budget: int = 30


class RepoSourceIn(BaseModel):
    repo_url: str
    ref: str = "main"
    token: str | None = None


class RubricIn(BaseModel):
    text: str
    source_ref: str


class CustomLensIn(BaseModel):
    description: str


class TargetIn(BaseModel):
    lens_id: str
    label: str
    deadline: date | None = None


class ClaimsIn(BaseModel):
    pitch_text: str


class ExportIn(BaseModel):
    format_id: str = "markdown"
    confirmed_fact_ids: list[str] = []


@router.post("/projects")
async def post_project(body: ProjectIn, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    project = await create_project(session, user, body.name)
    return {"id": project.id, "name": project.name}


@router.get("/projects")
async def get_projects(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    from ..models import ProjectMember

    rows = (
        await session.execute(select(ProjectMember).where(ProjectMember.user_id == user.id))
    ).scalars().all()
    return [{"project_id": r.project_id, "role": r.role} for r in rows]


@router.post("/projects/{project_id}/sources/text")
async def post_text_source(
    project_id: str,
    body: TextSourceIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_project_access(user, project_id, session)
    source = await add_text_source(session, project_id, body.text, body.label)
    return {"source_id": source.id, "kind": "text"}


@router.post("/projects/{project_id}/sources/doc")
async def post_doc_source(
    project_id: str,
    body: DocSourceIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """md, txt, json, and pasted text parse locally; pdf and docx go through
    firecrawl when a key is configured."""
    await require_project_access(user, project_id, session)
    if body.text is None and body.content_b64 is None:
        raise HTTPException(422, "send either text or content_b64")
    try:
        source = await add_doc_source(session, project_id, body.filename, text=body.text, content_b64=body.content_b64)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return {"source_id": source.id, "kind": "doc"}


@router.post("/projects/{project_id}/sources/url")
async def post_url_source(
    project_id: str,
    body: UrlSourceIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_project_access(user, project_id, session)
    try:
        source = await add_url_source(session, project_id, body.url)
    except Exception as e:  # noqa: ble001 - url failures are user-facing
        raise HTTPException(502, f"could not fetch {body.url}: {e}") from e
    return {"source_id": source.id, "kind": "url"}


@router.post("/projects/{project_id}/sources/docsite")
async def post_docsite_source(
    project_id: str,
    body: DocsiteIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """a bounded same-root crawl. runs as a job: crawls take as long as they
    take, and the job row is how progress is visible."""
    await require_project_access(user, project_id, session)
    job = await enqueue_job(session, "crawl_docsite", project_id, {"root_url": body.root_url, "budget": body.budget})
    return {"job_id": job.id, "status": job.status}


@router.post("/projects/{project_id}/sources/repo")
async def post_repo_source(
    project_id: str,
    body: RepoSourceIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_project_access(user, project_id, session)
    job = await enqueue_job(session, "sync_repo", project_id, {"repo_url": body.repo_url, "ref": body.ref, "token": body.token})
    return {"job_id": job.id, "status": job.status}


@router.get("/projects/{project_id}/grounding")
async def get_grounding(
    project_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """the nine w's coverage check: grounded, partial, or silent per dimension,
    with what would close each silent one."""
    await require_project_access(user, project_id, session)
    return await grounding_for_project(session, project_id)


@router.post("/projects/{project_id}/extract")
async def post_extract(
    project_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """runs the three passes and stores an immutable model version."""
    await require_project_access(user, project_id, session)
    facts = await extract_facts(session, project_id, runner(session))
    return {"facts": len(facts)}


@router.get("/projects/{project_id}/facts")
async def get_facts(
    project_id: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_project_access(user, project_id, session)
    facts = await list_facts(session, project_id)
    return [
        {"id": f.id, "kind": f.kind, "statement": f.statement, "confidence": f.confidence, "status": f.status, "provenance": f.provenance}
        for f in facts
    ]


@router.post("/lenses/parse-rubric")
async def post_parse_rubric(
    body: RubricIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from .. import brain
    from ..service import lens_out

    draft = await brain.lens_builder.parse_rubric(body.text, body.source_ref, runner(session))
    row = await save_lens_draft(session, draft, owner_id=user.id)
    return lens_out(row).model_dump()


@router.post("/lenses/draft-custom")
async def post_draft_custom(
    body: CustomLensIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from .. import brain
    from ..service import lens_out

    draft = await brain.lens_builder.draft_custom_lens(body.description, runner(session))
    row = await save_lens_draft(session, draft, owner_id=user.id)
    return lens_out(row).model_dump()


@router.get("/lenses/{lens_id}")
async def get_lens(lens_id: str, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    from ..service import lens_out

    row = await session.get(Lens, lens_id)
    if row is None:
        raise HTTPException(404, "lens not found")
    return lens_out(row).model_dump()


@router.post("/lenses/{lens_id}/confirm")
async def post_confirm_lens(lens_id: str, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """the mandatory review step: a draft lens never scores. confirmation means
    a human has confirmed or edited the parse, including every inferred weight."""
    row = await session.get(Lens, lens_id)
    if row is None:
        raise HTTPException(404, "lens not found")
    row = await confirm_lens_row(session, row)
    return {"id": row.id, "review_status": row.review_status}


@router.post("/projects/{project_id}/targets")
async def post_target(
    project_id: str,
    body: TargetIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_project_access(user, project_id, session)
    row = await create_target(session, project_id, body.lens_id, body.label, body.deadline)
    return {"id": row.id, "label": row.label}


@router.post("/targets/{target_id}/score")
async def post_score(target_id: str, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    target = await session.get(Target, target_id)
    if target is None:
        raise HTTPException(404, "target not found")
    try:
        row = await score_target_rows(session, target, runner(session))
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return {
        "id": row.id,
        "target_id": row.target_id,
        "model_version_id": row.model_version_id,
        "per_criterion": row.per_criterion,
        "weighted_total": row.weighted_total,
        "confidence": row.confidence,
    }


@router.get("/targets/{target_id}/gaps")
async def get_gaps(target_id: str, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Gap).where(Gap.target_id == target_id))).scalars().all()
    return [{"criterion": g.criterion, "weight": g.weight, "missing": g.missing, "would_close": g.would_close} for g in rows]


@router.post("/targets/{target_id}/pitch")
async def post_pitch(target_id: str, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    target = await session.get(Target, target_id)
    if target is None:
        raise HTTPException(404, "target not found")
    row = await generate_view_row(session, target, runner(session))
    return {
        "id": row.id,
        "sections": row.sections,
        "sentences": row.sentences,
        "annotations": row.annotations,
    }


@router.post("/targets/{target_id}/check-claims")
async def post_claims(
    target_id: str,
    body: ClaimsIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    target = await session.get(Target, target_id)
    if target is None:
        raise HTTPException(404, "target not found")
    rows = await check_claims_rows(session, target, body.pitch_text, runner(session))
    return [
        {"claim": c.claim_text, "verdict": c.verdict, "fact_ids": c.fact_ids, "rewrite": c.suggested_rewrite}
        for c in rows
    ]


@router.post("/views/{view_id}/export")
async def post_export(
    view_id: str,
    body: ExportIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from ..service import export_view_row

    try:
        row = await export_view_row(session, view_id, body.format_id, body.confirmed_fact_ids)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"id": row.id, "format_id": row.format_id, "body": row.body}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    row = await session.get(Job, job_id)
    if row is None:
        raise HTTPException(404, "job not found")
    return {"id": row.id, "kind": row.kind, "status": row.status, "progress": row.progress, "error": row.error}
