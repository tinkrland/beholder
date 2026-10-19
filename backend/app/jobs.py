"""the job worker. one queue, one worker type for the mvp. we own the runtime,
so there are no execution time limits: a job runs to completion, and the job
rows are how users see progress and how failures resume from the last
finished chunk."""

import asyncio

from sqlalchemy import select

from .db import Session
from .models import Job
from .service import sync_repo_source


async def process_one(session) -> Job | None:
    row = (
        await session.execute(select(Job).where(Job.status == "pending").order_by(Job.created_at).limit(1))
    ).scalar_one_or_none()
    if row is None:
        return None
    row.status = "running"
    await session.commit()

    try:
        if row.kind == "sync_repo":
            src = await sync_repo_source(
                session,
                row.project_id,
                row.payload["repo_url"],
                row.payload.get("ref", "main"),
                row.payload.get("token"),
            )
            row.progress = {"source_id": src.id}
        else:
            raise ValueError(f"unknown job kind: {row.kind}")
        row.status = "done"
    except Exception as e:  # noqa: ble001 - the job row is the error surface
        row.status = "failed"
        row.error = str(e)
    await session.commit()
    return row


async def worker_loop(poll_seconds: float = 1.0) -> None:
    """runs forever. the api starts this in-process when inline_worker is on."""
    while True:
        async with Session() as session:
            processed = await process_one(session)
        if processed is None:
            await asyncio.sleep(poll_seconds)


def start_inline_worker() -> asyncio.Task:
    return asyncio.create_task(worker_loop())
