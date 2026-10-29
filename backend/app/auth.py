"""the api verifies jwts issued by supabase auth against standard jwks. the api
never manages sessions itself. dev_auth skips verification for local runs and
tests only, and is off by default."""

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .models import ProjectMember, User


def _fetch_jwks(url: str) -> dict:
    with httpx.Client(timeout=15) as client:
        r = client.get(f"{url}/auth/v1/.well-known/jwks.json")
        r.raise_for_status()
        return r.json()


def verify_token(token: str) -> dict:
    if settings.dev_auth:
        # local mode: no signature to verify, the caller is whoever they say
        if token.count(".") == 2:
            return jwt.decode(token, options={"verify_signature": False})
        # a dev token that already looks like an email keeps it: allowlists
        # and reviewer checks compare on email, and mangling it would make
        # the same identity unreachable in dev and prod alike.
        email = token if "@" in token else f"{token or 'dev'}@dev.local"
        return {"sub": token or "dev", "email": email}
    if not settings.supabase_url:
        raise HTTPException(status_code=501, detail="auth is not configured: set supabase_url or enable dev_auth locally")
    jwks = _fetch_jwks(settings.supabase_url)
    try:
        return jwt.decode(
            token,
            key=jwks,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_audience,
            options={"verify_aud": False},  # audience differs per setup; sub is the contract here
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}") from e


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    """the bearer token becomes a user row. auth_id is the stable key."""
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("bearer ").removeprefix("Bearer ").strip() or "dev"
    claims = verify_token(token)
    auth_id = claims.get("sub") or claims.get("email") or "dev"
    user = (await session.execute(select(User).where(User.auth_id == auth_id))).scalar_one_or_none()
    if user is None:
        email = claims.get("email") or f"{auth_id}@dev.local"
        # the same identity can arrive spelled two ways (a dev token that is
        # an email, and the bare name it was minted from). email is unique,
        # so adopt the existing row instead of colliding on the constraint.
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(auth_id=auth_id, email=email)
            session.add(user)
            await session.commit()
    return user


async def require_project_access(user: User, project_id: str, session: AsyncSession) -> None:
    """solo-first: v1 checks the membership table; a missing row is a 404,
    not a 403: projects you cannot see do not exist to you."""
    member = (
        await session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="project not found")
