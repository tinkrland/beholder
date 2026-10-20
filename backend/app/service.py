"""service layer: the only place that touches both the db and the brain.
routes call these; nothing else does."""

import hashlib
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import brain
from .config import settings
from .db import Json  # noqa: F401  (type registration)
from .ingest import repo_walk as walk_mod
from .ingest.forge import FORGES, _env_tokens, forge_for_url, forge_name_for_url
from .presets import load_presets, preset_by_key
from .ingest.docsite import crawl as crawl_docsite
from .ingest.docs import parse_direct_text, parse_document
from .ingest.firecrawl import FirecrawlClient
from .ingest.html import html_to_text
from .ingest.secrets import redact
from .models import (
    ForgeAccount,
    ClaimCheck,
    Fact,
    Gap,
    Job,
    Lens,
    ModelVersion,
    PitchView,
    Project,
    ProjectMember,
    Score,
    Source,
    SourceChunk,
    Target,
    Export,
    uid,
)
from .schemas import FactOut, LensOut, PitchViewOut, Provenance


def _content_hash(statement: str, provenance: list) -> str:
    return hashlib.sha256(json.dumps({"s": statement, "p": [p.model_dump() for p in provenance]}, sort_keys=True).encode()).hexdigest()


def fact_out(row: Fact) -> FactOut:
    return FactOut(
        id=row.id,
        project_id=row.project_id,
        kind=row.kind,
        statement=row.statement,
        value=row.value,
        provenance=[Provenance(**p) for p in row.provenance],
        confidence=row.confidence,
        status=row.status,
        content_hash=row.content_hash,
    )


async def create_project(session: AsyncSession, user, name: str) -> Project:
    project = Project(name=name)
    session.add(project)
    await session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    await session.commit()
    return project


async def add_text_source(session: AsyncSession, project_id: str, text: str, label: str) -> Source:
    text, _ = redact(text)
    source = Source(
        project_id=project_id,
        kind="text",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        meta={"label": label},
    )
    session.add(source)
    await session.flush()
    # pasted text is user-stated: provenance type user, shown as such
    for i, c in enumerate(parse_direct_text(text, label, kind="user")):
        session.add(SourceChunk(source_id=source.id, idx=i, path=label, lines_start=c["lines_start"], lines_end=c["lines_end"], text=c["text"], kind=c.get("kind", "user")))
    await session.commit()
    return source


async def add_doc_source(session: AsyncSession, project_id: str, filename: str, text: str | None = None, content_b64: str | None = None, firecrawl: FirecrawlClient | None = None) -> Source:
    """md, txt, json direct; pdf, docx through firecrawl. every chunk keeps
    doc provenance: the filename is the ref."""
    chunks = await parse_document(filename, text=text, content_b64=content_b64, firecrawl=firecrawl)
    cleaned = []
    for c in chunks:
        clean, _ = redact(c["text"])
        cleaned.append({**c, "text": clean})
    source = Source(
        project_id=project_id,
        kind="doc",
        url=filename,
        content_hash=hashlib.sha256("".join(c["text"] for c in cleaned).encode()).hexdigest(),
        meta={"filename": filename},
    )
    session.add(source)
    await session.flush()
    for i, c in enumerate(cleaned):
        session.add(SourceChunk(source_id=source.id, idx=i, path=filename, lines_start=c["lines_start"], lines_end=c["lines_end"], text=c["text"], kind="doc", page=c.get("page")))
    await session.commit()
    return source


async def add_url_source(session: AsyncSession, project_id: str, url: str, firecrawl: FirecrawlClient | None = None, client=None) -> Source:
    """one page as a source. html pages parse locally; pdfs go through
    firecrawl. provenance is the url itself."""
    import httpx

    if url.lower().endswith(".pdf"):
        markdown = await (firecrawl or FirecrawlClient()).scrape_markdown(url)
        text = markdown
    else:
        own = client
        if own is None:
            own = httpx.AsyncClient(timeout=30, follow_redirects=True)
        try:
            r = await own.get(url)
            r.raise_for_status()
            text = html_to_text(r.text) if "html" in r.headers.get("content-type", "") else r.text
        finally:
            if client is None:
                await own.aclose()
    text, _ = redact(text)
    source = Source(
        project_id=project_id,
        kind="url",
        url=url,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        meta={},
    )
    session.add(source)
    await session.flush()
    for i, c in enumerate(parse_direct_text(text, url, kind="url")):
        session.add(SourceChunk(source_id=source.id, idx=i, path=url, lines_start=c["lines_start"], lines_end=c["lines_end"], text=c["text"], kind="url"))
    await session.commit()
    return source


async def crawl_docsite_source(session: AsyncSession, project_id: str, root_url: str, budget: int = 30, client=None) -> Source:
    """a bounded same-root crawl of a doc site (gitbook, quartz). each page
    is stored as its own url chunk; the unread report is kept in source.meta."""
    result = await crawl_docsite(root_url, budget=budget, client=client)
    pages, report = result["pages"], result["report"]
    source = Source(
        project_id=project_id,
        kind="url",
        url=root_url,
        content_hash=hashlib.sha256("".join(p["text"] for p in pages).encode()).hexdigest(),
        meta={"report": {k: v for k, v in report.items() if k != "unread_budget"} | {"unread_budget_count": len(report.get("unread_budget", []))}},
    )
    session.add(source)
    await session.flush()
    idx = 0
    for p in pages:
        for c in parse_direct_text(p["text"], p["url"], kind="url"):
            session.add(SourceChunk(source_id=source.id, idx=idx, path=p["url"], lines_start=c["lines_start"], lines_end=c["lines_end"], text=c["text"], kind="url"))
            idx += 1
    await session.commit()
    return source


async def upsert_forge_account(session: AsyncSession, user_id: str, forge: str, token: str) -> ForgeAccount:
    """one connected account per user and forge. upsert keeps the newest
    token: rotating a credential is a replace, not an accumulation."""
    if forge not in FORGES:
        raise ValueError(f"unknown forge: {forge}")
    row = (await session.execute(select(ForgeAccount).where(ForgeAccount.user_id == user_id, ForgeAccount.forge == forge))).scalar_one_or_none()
    if row:
        row.token = token
    else:
        row = ForgeAccount(user_id=user_id, forge=forge, token=token)
        session.add(row)
    await session.commit()
    return row


async def list_forge_accounts(session: AsyncSession, user_id: str) -> list[ForgeAccount]:
    return (await session.execute(select(ForgeAccount).where(ForgeAccount.user_id == user_id).order_by(ForgeAccount.forge))).scalars().all()


async def delete_forge_account(session: AsyncSession, user_id: str, forge: str) -> bool:
    """revocation is immediate and complete: the token row is deleted, not
    flagged. private repos become unreadable the next sync."""
    row = (await session.execute(select(ForgeAccount).where(ForgeAccount.user_id == user_id, ForgeAccount.forge == forge))).scalar_one_or_none()
    if not row:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def resolve_forge_token(session: AsyncSession, user_id: str, forge: str, explicit: str | None = None) -> str | None:
    """token priority: the token passed with the request, then the connected
    account, then the instance env token, then anonymous. the account wins
    over env so a hosted deploy can serve many users with one fallback."""
    if explicit:
        return explicit
    row = (await session.execute(select(ForgeAccount).where(ForgeAccount.user_id == user_id, ForgeAccount.forge == forge))).scalar_one_or_none()
    if row:
        return row.token
    return _env_tokens().get(forge)


async def sync_repo_source(session: AsyncSession, project_id: str, repo_url: str, ref: str, token: str | None = None, forge: str | None = None) -> Source:
    """the rest walk: tree, excludes, selected blobs, redaction, chunks. any
    forge: the adapter follows the repo url, github, gitlab, bitbucket, or
    gitea. the unread report is stored in source.meta, not dropped."""
    name = forge_name_for_url(repo_url, forge)
    result = walk_mod.walk_repo(repo_url, ref, forge=forge_for_url(repo_url, token=token, override=forge))
    chunks, report = result["chunks"], result["report"]
    source = Source(
        project_id=project_id,
        kind="repo",
        forge=name,
        ref=ref,
        url=repo_url,
        commit_sha=report.get("commit_sha"),
        content_hash=hashlib.sha256("\n".join(c["text"] for c in chunks).encode()).hexdigest(),
        meta={"report": {k: v for k, v in report.items() if k != "skipped_excluded"} | {"skipped_excluded_count": len(report.get("skipped_excluded", []))}},
    )
    session.add(source)
    await session.flush()
    for i, c in enumerate(chunks):
        session.add(SourceChunk(source_id=source.id, idx=i, path=c["path"], lines_start=c["lines_start"], lines_end=c["lines_end"], text=c["text"], redacted=c.get("redacted", False)))
    await session.commit()
    return source


async def extract_facts(session: AsyncSession, project_id: str, run) -> list[Fact]:
    """static pass, structural pass, semantic pass, then an immutable model
    version. user-confirmed facts outrank inferred on re-extraction: the
    content hash keeps them identical across runs."""
    chunks = (
        await session.execute(
            select(SourceChunk, Source).join(Source).where(Source.project_id == project_id).order_by(Source.created_at, SourceChunk.source_id, SourceChunk.idx)
        )
    ).all()
    chunk_dicts = [
        {
            "source_id": source.id,
            "source_kind": source.kind,
            "path": c.path or "",
            "text": c.text,
            "lines_start": c.lines_start or 0,
            "lines_end": c.lines_end or 0,
            "commit_sha": None,
            "kind": c.kind or "file",
            "page": c.page,
        }
        for c, source in chunks
    ]
    static = brain.extraction.static_pass(chunk_dicts)
    paths = sorted({c["path"] for c in chunk_dicts if c["path"]})
    structural = brain.extraction.structural_pass(paths)

    existing = (await session.execute(select(Fact).where(Fact.project_id == project_id))).scalars().all()
    confirmed_hashes = {f.content_hash for f in existing if f.status == "confirmed"}
    rejected_hashes = {f.content_hash for f in existing if f.status == "rejected"}

    semantic = await brain.extraction.semantic_pass(
        brain.extraction.select_semantic_chunks(chunk_dicts, settings.semantic_chunks), project_id, run
    )

    stored: list[Fact] = []
    for f in [*static, *structural, *semantic]:
        h = _content_hash(f.statement, f.provenance)
        if h in rejected_hashes:
            continue  # rejected facts stay rejected unless provenance changes
        status = "confirmed" if h in confirmed_hashes else f.status
        row = Fact(
            id=uid(),
            project_id=project_id,
            kind=f.kind,
            statement=f.statement,
            value=f.value,
            provenance=[p.model_dump() for p in f.provenance],
            confidence=f.confidence,
            status=status,
            content_hash=h,
        )
        session.add(row)
        stored.append(row)
    await session.flush()

    sources = (await session.execute(select(Source).where(Source.project_id == project_id))).scalars().all()
    version = ModelVersion(
        project_id=project_id,
        fact_ids=[f.id for f in stored],
        source_hashes=[s.content_hash for s in sources],
    )
    session.add(version)
    await session.commit()
    return stored


async def ensure_presets(session: AsyncSession) -> list[Lens]:
    """sync authored preset files into the lenses table. upsert keyed by name
    with owner_id null and type preset: a changed file bumps the version and
    replaces the content, targets keep pointing at the lens id."""
    rows = []
    for preset in load_presets():
        row = (
            await session.execute(select(Lens).where(Lens.type == "preset", Lens.name == preset["key"], Lens.owner_id.is_(None)))
        ).scalar_one_or_none()
        if row is None:
            row = Lens(
                owner_id=None,
                type="preset",
                name=preset["key"],
                sources=[{"ref": u} for u in preset["sources"]],
                criteria=preset["criteria"],
                required_questions=preset["required_questions"],
                red_flags=preset["red_flags"],
                objection_seeds=preset["objection_seeds"],
                trusted_evidence=preset["trusted_evidence"],
                vocabulary=preset["vocabulary"],
                output_formats=preset["output_formats"],
                review_status="confirmed",  # authored by a human, not drafted by a model
                visibility="shared",  # visible to every user: the library
                last_verified=None,
                staleness_days=preset["staleness_days"],
            )
            session.add(row)
        else:
            changed = (
                row.criteria != preset["criteria"]
                or row.objection_seeds != preset["objection_seeds"]
                or row.red_flags != preset["red_flags"]
                or row.trusted_evidence != preset["trusted_evidence"]
            )
            if changed:
                row.version += 1
                row.criteria = preset["criteria"]
                row.objection_seeds = preset["objection_seeds"]
                row.red_flags = preset["red_flags"]
                row.trusted_evidence = preset["trusted_evidence"]
                row.sources = [{"ref": u} for u in preset["sources"]]
                row.staleness_days = preset["staleness_days"]
        rows.append(row)
    await session.commit()
    return rows


async def list_presets(session: AsyncSession) -> list[dict]:
    """the presets listing with staleness, per brain.presets.preset_summary.
    ensure first so the listing reflects the authored files."""
    rows = await ensure_presets(session)
    by_key = {r.name: r for r in rows}
    return [brain.presets.preset_summary(p, {"id": by_key[p["key"]].id, "version": by_key[p["key"]].version, "last_verified": by_key[p["key"]].last_verified}) for p in load_presets()]


async def refresh_presets(session: AsyncSession, keys: list[str] | None = None, client=None) -> dict:
    """the staleness refresh: fetch each preset's sources, run the dumb drift
    check, and set last_verified when the sources still resolve. a drifted
    preset stays stale: a human re-reads it, the refresh never rewrites
    criteria on its own."""
    import httpx

    rows = await ensure_presets(session)
    by_key = {r.name: r for r in rows}
    wanted = keys or [p["key"] for p in load_presets()]
    results = []
    own = client
    if own is None:
        own = httpx.AsyncClient(timeout=30, follow_redirects=True)
    try:
        for key in wanted:
            preset = preset_by_key(key)
            if preset is None:
                results.append({"key": key, "error": "unknown preset"})
                continue
            row = by_key[key]
            texts: list[str] = []
            fetch_errors: list[str] = []
            if not preset["sources"]:
                row.last_verified = date.today()
                results.append({"key": key, "verified": str(row.last_verified), "checkable": False, "note": "no sources: verified by re-read"})
                continue
            for url in preset["sources"]:
                try:
                    r = await own.get(url)
                    r.raise_for_status()
                    body = r.text if "html" not in r.headers.get("content-type", "") else None
                    if body is None:
                        from .ingest.html import html_to_text

                        body = html_to_text(r.text)
                    texts.append(body)
                except httpx.HTTPError as e:
                    fetch_errors.append(f"{url}: {e}")
            drift = brain.presets.drift_check(preset, texts)
            if fetch_errors or drift["drifted"]:
                row.last_verified = row.last_verified  # stays stale: honest, not patched
                results.append({"key": key, "error": "; ".join(fetch_errors) if fetch_errors else None, **drift, "verified": None})
            else:
                row.last_verified = date.today()
                results.append({"key": key, **drift, "verified": str(row.last_verified)})
    finally:
        if client is None:
            await own.aclose()
    await session.commit()
    return {"refreshed": results, "date": str(date.today())}


async def consistency_report(session: AsyncSession, project_id: str, run) -> dict:
    """one project, many readers, one story. the latest view per target is
    compared view against view; contradictions are reported, never rewritten.
    views are immutable, so the report is derived on demand, not stored."""
    from .models import PitchView, Target

    rows = (
        await session.execute(
            select(PitchView, Target)
            .join(Target, PitchView.target_id == Target.id)
            .where(Target.project_id == project_id)
            .order_by(PitchView.created_at.desc())
        )
    ).all()
    latest: dict[str, tuple] = {}
    for view, target in rows:
        if view.target_id not in latest:  # ordered desc: first seen is the newest
            latest[view.target_id] = (view, target)
    views = [
        {"target_id": view.target_id, "label": target.label, "sentences": view.sentences}
        for view, target in latest.values()
    ]
    report = await brain.consistency.check_consistency(views, run)
    report["project_id"] = project_id
    return report


async def grounding_for_project(session: AsyncSession, project_id: str) -> dict:
    """the nine w's coverage check over the project's fact set."""
    facts = await load_facts_for_model(session, project_id, None)
    return brain.grounding.ground(facts)


async def matching_for_project(session: AsyncSession, project_id: str) -> dict:
    """the matching report: scored targets ranked by fit, library presets
    suggested by readiness, unscored targets named. no model calls: the
    report is arithmetic over scores and grounding."""
    targets = (await session.execute(select(Target).where(Target.project_id == project_id).order_by(Target.created_at))).scalars().all()
    scored: list[dict] = []
    unscored: list[dict] = []
    for t in targets:
        score_row = (
            await session.execute(select(Score).where(Score.target_id == t.id).order_by(Score.created_at.desc()))
        ).scalars().first()
        if score_row is None:
            unscored.append({"target_id": t.id, "label": t.label})
            continue
        gap_rows = (await session.execute(select(Gap).where(Gap.target_id == t.id).order_by(Gap.created_at.desc()))).scalars().all()
        top_gap = None
        if gap_rows:
            best = max(gap_rows, key=lambda g: g.weight)
            top_gap = {"criterion": best.criterion, "weight": best.weight, "missing": best.missing, "would_close": best.would_close}
        scored.append(
            {
                "target_id": t.id,
                "label": t.label,
                "lens_id": t.lens_id,
                "deadline": t.deadline.isoformat() if t.deadline else None,
                "weighted_total": score_row.weighted_total,
                "confidence": score_row.confidence,
                "top_gap": top_gap,
            }
        )
    grounding = await grounding_for_project(session, project_id)
    preset_lens = (await session.execute(select(Lens).where(Target.project_id == project_id, Lens.id == Target.lens_id, Lens.type == "preset"))).scalars().all()
    attached_keys = {row.name for row in preset_lens}
    return brain.matching.match(scored, load_presets(), grounding, attached_keys, unscored)


async def list_facts(session: AsyncSession, project_id: str) -> list[Fact]:
    return (await session.execute(select(Fact).where(Fact.project_id == project_id).order_by(Fact.kind))).scalars().all()


async def save_lens_draft(session: AsyncSession, draft, owner_id: str | None) -> Lens:
    row = Lens(
        owner_id=owner_id,
        type=draft.type,
        name=draft.name,
        criteria=[c.model_dump() for c in draft.criteria],
        required_questions=draft.required_questions,
        required_artifacts=draft.required_artifacts,
        impresses=draft.impresses,
        red_flags=draft.red_flags,
        alternatives_frame=draft.alternatives_frame,
        trusted_evidence=draft.trusted_evidence,
        objection_seeds=draft.objection_seeds,
        vocabulary=draft.vocabulary,
        output_formats=draft.output_formats,
        sources=draft.sources,
        last_verified=draft.last_verified or date.today(),
        review_status="draft",
        inferred_fields=draft.inferred_fields,
    )
    session.add(row)
    await session.commit()
    return row


def lens_out(row: Lens) -> LensOut:
    return LensOut(
        id=row.id,
        owner_id=row.owner_id,
        type=row.type,
        name=row.name,
        version=row.version,
        criteria=row.criteria,
        required_questions=row.required_questions,
        required_artifacts=row.required_artifacts,
        impresses=row.impresses,
        red_flags=row.red_flags,
        alternatives_frame=row.alternatives_frame,
        trusted_evidence=row.trusted_evidence,
        objection_seeds=row.objection_seeds,
        vocabulary=row.vocabulary,
        output_formats=row.output_formats,
        sources=row.sources,
        last_verified=row.last_verified,
        staleness_days=row.staleness_days,
        visibility=row.visibility,
        review_status=row.review_status,
        inferred_fields=row.inferred_fields or [],
        created_at=row.created_at,
    )


def _check_weights(criteria: list) -> None:
    """the one rule every lens shares with every authored preset: weights sum
    to 1.0. a wrong sum silently skews every score, so it is rejected here,
    not smoothed."""
    if not criteria:
        raise ValueError("a lens with no criteria cannot be confirmed")
    weights = sum(c.weight for c in criteria)
    if abs(weights - 1.0) > 0.001:
        raise ValueError(f"weights sum to {round(weights, 4)}, not 1.0")
    if any(c.weight <= 0 for c in criteria):
        raise ValueError("every criterion needs a positive weight")


async def update_lens_draft(session: AsyncSession, lens: Lens, edit) -> Lens:
    """the review step's edit half. only drafts are editable: a confirmed
    lens has scores resting on it, and edits to it are a new version. a
    weight the human changes stops being inferred: the marker records
    where the number came from."""
    if lens.review_status != "draft":
        raise ValueError("only a draft lens is editable: re-parse into a new lens instead")
    _check_weights(edit.criteria)
    old_weights = {c["name"]: c["weight"] for c in lens.criteria}
    for c in edit.criteria:
        if old_weights.get(c.name) != c.weight:
            c.inferred_weight = False  # the human set this one
    lens.criteria = [c.model_dump() for c in edit.criteria]
    for field in ("required_questions", "required_artifacts", "impresses", "red_flags", "alternatives_frame", "trusted_evidence", "objection_seeds", "vocabulary", "output_formats"):
        v = getattr(edit, field)
        if v is not None:
            setattr(lens, field, v)
    await session.commit()
    return lens


async def confirm_lens_row(session: AsyncSession, lens: Lens, echoed: list[tuple[str, float]]) -> Lens:
    """the review step. confirmation must echo the current criteria, name and
    weight each: the reviewer read the weights, including the inferred ones.
    a mismatch is a reject, never a silent confirm."""
    draft = lens_out(lens)
    brain.lens_builder.confirm_lens(draft)
    _check_weights(draft.criteria)
    current = {c.name: round(c.weight, 6) for c in draft.criteria}
    echoed = {name: round(weight, 6) for name, weight in echoed}
    missing = sorted(set(current) - set(echoed))
    if missing:
        raise ValueError(f"confirmation must name every criterion with its current weight, missing: {missing}")
    wrong = {name: (echoed[name], current[name]) for name in current if echoed[name] != current[name]}
    if wrong:
        detail = ", ".join(f"{name}: echoed {echoed[name]}, lens says {current[name]}" for name in sorted(wrong))
        raise ValueError(f"the echoed weights do not match the lens, re-render and confirm what you reviewed: {detail}")
    lens.review_status = "confirmed"
    await session.commit()
    return lens


async def create_target(session: AsyncSession, project_id: str, lens_id: str, label: str, deadline=None) -> Target:
    row = Target(project_id=project_id, lens_id=lens_id, label=label, deadline=deadline)
    session.add(row)
    await session.commit()
    return row


async def load_facts_for_model(session: AsyncSession, project_id: str, model_version_id: str | None) -> list[FactOut]:
    if model_version_id:
        version = await session.get(ModelVersion, model_version_id)
        if version is None:
            raise ValueError("model version not found")
        rows = (await session.execute(select(Fact).where(Fact.id.in_(version.fact_ids)))).scalars().all()
    else:
        rows = await list_facts(session, project_id)
    return [fact_out(r) for r in rows]


async def score_target_rows(session: AsyncSession, target: Target, run) -> Score:
    lens_row = await session.get(Lens, target.lens_id)
    lens = lens_out(lens_row)
    if lens.review_status != "confirmed":
        raise ValueError("a draft lens never scores: confirm the parse, including every inferred weight, first")
    facts = await load_facts_for_model(session, target.project_id, None)
    latest_version = (
        await session.execute(select(ModelVersion).where(ModelVersion.project_id == target.project_id).order_by(ModelVersion.created_at.desc()))
    ).scalars().first()
    score, gaps = await brain.scorer.score_target(target.id, latest_version.id if latest_version else "", facts, lens, run)

    row = Score(
        target_id=target.id,
        model_version_id=latest_version.id if latest_version else "",
        per_criterion=[c.model_dump() for c in score.per_criterion],
        weighted_total=score.weighted_total,
        confidence=score.confidence,
    )
    session.add(row)
    for g in gaps:
        session.add(Gap(target_id=target.id, criterion=g.criterion, weight=g.weight, missing=g.missing, would_close=g.would_close))
    await session.commit()
    return row


async def generate_view_row(session: AsyncSession, target: Target, run) -> PitchView:
    lens_row = await session.get(Lens, target.lens_id)
    lens = lens_out(lens_row)
    facts = await load_facts_for_model(session, target.project_id, None)
    latest_version = (
        await session.execute(select(ModelVersion).where(ModelVersion.project_id == target.project_id).order_by(ModelVersion.created_at.desc()))
    ).scalars().first()
    view = await brain.projector.project(target.id, latest_version.id if latest_version else "", facts, lens, run)
    row = PitchView(
        target_id=target.id,
        model_version_id=view.model_version_id,
        lens_version=lens.version,
        sections=[s.model_dump() for s in view.sections],
        sentences=[s.model_dump() for s in view.sentences],
        annotations=view.annotations,
        stale=False,
        cache_key=view.cache_key,
    )
    session.add(row)
    await session.commit()
    return row


async def check_claims_rows(session: AsyncSession, target: Target, pitch_text: str, run) -> list[ClaimCheck]:
    facts = await load_facts_for_model(session, target.project_id, None)
    checks = await brain.claims.check_claims(pitch_text, facts, run)
    rows = []
    for c in checks:
        row = ClaimCheck(target_id=target.id, claim_text=c.claim_text, verdict=c.verdict, fact_ids=c.fact_ids, suggested_rewrite=c.suggested_rewrite)
        session.add(row)
        rows.append(row)
    await session.commit()
    return rows


async def export_view_row(session: AsyncSession, view_id: str, format_id: str, confirmed_fact_ids: list[str]) -> Export:
    """export passes the honesty guard or names exactly what blocks it."""
    view_row = await session.get(PitchView, view_id)
    if view_row is None:
        raise ValueError("view not found")
    target = await session.get(Target, view_row.target_id)
    facts = {f.id: f for f in await load_facts_for_model(session, target.project_id, None)}
    view = PitchViewOut(
        id=view_row.id,
        target_id=view_row.target_id,
        model_version_id=view_row.model_version_id,
        lens_version=view_row.lens_version,
        sections=view_row.sections,
        sentences=view_row.sentences,
        stale=view_row.stale,
        cache_key=view_row.cache_key,
    )
    report = brain.honesty.can_export(view, facts, confirmed_fact_ids)
    if not report.exportable:
        raise PermissionError("export blocked: " + "; ".join(report.blocking))
    body = "\n\n".join(
        f"## {section.key}\n"
        + "\n".join(next(x.text for x in view.sentences if x.id == sid) for sid in section.sentence_ids)
        for section in view.sections
        if section.sentence_ids
    )
    row = Export(view_id=view_id, format_id=format_id, body=body, confirmed_unsupported=confirmed_fact_ids)
    session.add(row)
    await session.commit()
    return row


async def enqueue_job(session: AsyncSession, kind: str, project_id: str | None, payload: dict, user_id: str | None = None) -> Job:
    row = Job(kind=kind, project_id=project_id, user_id=user_id, payload=payload)
    session.add(row)
    await session.commit()
    return row
