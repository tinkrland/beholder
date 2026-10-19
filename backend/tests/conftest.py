"""test configuration. the gateway is mocked everywhere: no model calls, no
network. brain tests run against canned runners; the api flow runs against a
temp sqlite database."""

import json
import os

os.environ["BEHOLDER_DEV_AUTH"] = "true"
os.environ["BEHOLDER_GATEWAY_PROVIDER"] = "mock"
os.environ["BEHOLDER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["BEHOLDER_INLINE_WORKER"] = "false"

import pytest  # noqa: E402


def canned_responder(spec, user_content):
    """tests use the demo responder so the canned path stays in one place."""
    from app.gateway.demo import demo_responder

    return demo_responder(spec, user_content)


class FakeRun:
    """a canned runner for brain unit tests: keyed by task id."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls = []

    async def __call__(self, task_id, payload):
        self.calls.append((task_id, payload))
        value = self.responses[task_id]
        if callable(value):
            value = value(payload)
        return value


@pytest.fixture
async def db_session():
    from app.db import Base, engine
    from app import models  # noqa: F401  (register every table before create_all)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.db import Session

    async with Session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
