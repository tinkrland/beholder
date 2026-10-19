"""database session. plain sqlalchemy, any postgres, sqlite for dev and tests."""

from collections.abc import AsyncIterator

from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from .config import settings


class Json(TypeDecorator):
    """jsonb on postgres, json elsewhere. the same data on any engine."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or settings.database_url
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    return create_async_engine(url, **kwargs)


engine = make_engine()
Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with Session() as session:
        yield session
