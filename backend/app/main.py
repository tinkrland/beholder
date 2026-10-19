"""beholder api. fastapi, one service, any postgres."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.inline_worker:
        from .jobs import start_inline_worker

        task = start_inline_worker()
    # dev convenience: create tables on startup. production runs alembic.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        if settings.inline_worker:
            task.cancel()


app = FastAPI(title="beholder", version="0.1.0", lifespan=lifespan)


from .api.routes import router  # noqa: E402

app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"ok": True}
