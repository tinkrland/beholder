"""gateway runtime: caching, metering, and the runner the brain receives.

the brain never sees providers or http. it receives a runner:
    async def run(task_id, payload) -> dict
the api wires the runner to this class; tests wire it to canned responses.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import GatewayCall
from . import TASKS, GlmProvider, MockProvider, cache_key, extract_json


class Gateway:
    def __init__(self, session: AsyncSession, provider: Any | None = None):
        self.session = session
        self.provider = provider or self._default_provider()

    def _default_provider(self):
        if settings.gateway_provider == "demo":
            from .demo import demo_responder

            return MockProvider(responder=demo_responder)
        if settings.gateway_provider == "mock":
            return MockProvider()
        return GlmProvider()

    async def run(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """returns the parsed json for the task. caching by cache key: the same
        task, prompt version, and payload never pay for the same call twice."""
        spec = TASKS[task_id]
        key = cache_key(task_id, payload)

        hit = await self.session.scalar(select(GatewayCall).where(GatewayCall.cache_key == key))
        if hit is not None:
            self.session.add(
                GatewayCall(
                    task_id=task_id,
                    cache_key=key,
                    result=hit.result,
                    cached=True,
                    prompt_version=spec.prompt_version,
                    model=hit.model,
                )
            )
            await self.session.commit()
            return hit.result

        user_content = spec.user_template.format(**payload)
        raw = await self.provider.complete(spec, user_content)
        parsed = extract_json(raw["content"])

        self.session.add(
            GatewayCall(
                task_id=task_id,
                cache_key=key,
                result=parsed,
                cached=False,
                prompt_version=spec.prompt_version,
                model=raw.get("model", "unknown"),
                in_tokens=raw.get("in_tokens", 0),
                out_tokens=raw.get("out_tokens", 0),
            )
        )
        await self.session.commit()
        return parsed


class SimpleRunner:
    """the runner the brain receives. binds a session and a gateway provider.
    in tests, brain functions receive any callable with the same signature."""

    def __init__(self, session: AsyncSession, provider: Any | None = None):
        self.gateway = Gateway(session, provider)

    async def __call__(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.gateway.run(task_id, payload)
