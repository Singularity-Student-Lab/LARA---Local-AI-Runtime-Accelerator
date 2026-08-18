"""FastAPI auth dependencies. Every failure path returns the same body shape for a given
status code so an enumerating attacker cannot distinguish "unknown key" from "wrong secret"
(blueprint section 3.4 point 5 / Testing T-S3-02 through T-S3-05)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.keys import parse_key, verify_secret
from app.config import get_settings
from app.db.models import ApiKey, Role, User
from app.db.session import get_db

_LAST_USED_UPDATE_GRANULARITY = timedelta(seconds=60)

_UNAUTHENTICATED = HTTPException(
    status_code=401,
    detail={"error": {"type": "unauthenticated", "message": "Authentication failed."}},
)


@dataclasses.dataclass
class AuthContext:
    user: User
    role: Role
    api_key: ApiKey


async def get_auth_context(request: Request, db: AsyncSession = Depends(get_db)) -> AuthContext:
    settings = get_settings()

    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise _UNAUTHENTICATED
    raw_key = header[len("Bearer ") :].strip()

    parsed = parse_key(raw_key)
    if parsed is None:
        raise _UNAUTHENTICATED
    key_id, secret = parsed

    api_key = (await db.execute(select(ApiKey).where(ApiKey.key_id == key_id))).scalar_one_or_none()
    if api_key is None:
        raise _UNAUTHENTICATED
    if api_key.revoked_at is not None:
        raise _UNAUTHENTICATED
    if not verify_secret(secret, api_key.secret_hash, settings.lara_api_key_pepper):
        raise _UNAUTHENTICATED

    user = (await db.execute(select(User).where(User.id == api_key.user_id))).scalar_one_or_none()
    if user is None:
        # Orphaned key - treat as unauthenticated, not a 500. Should not happen given the FK.
        raise _UNAUTHENTICATED
    if not user.enabled:
        raise HTTPException(
            status_code=403,
            detail={"error": {"type": "account_disabled", "message": "This account is disabled."}},
        )

    role = (await db.execute(select(Role).where(Role.id == user.role_id))).scalar_one_or_none()
    if role is None:
        raise _UNAUTHENTICATED

    # Coarse last_used_at update: skip the write if updated within the granularity window,
    # so key usage doesn't add a write to every single request (blueprint section 3.4 point 3).
    now = datetime.now(timezone.utc)
    if api_key.last_used_at is None or (now - api_key.last_used_at) > _LAST_USED_UPDATE_GRANULARITY:
        api_key.last_used_at = now
        await db.commit()

    # Per-key request-rate limiting (blueprint section 6, Session 6): limits arrival rate,
    # never a user's total useful work (PRD 9.6 - no token quota exists anywhere here).
    rate_limiter = getattr(request.app.state, "rate_limiter", None)
    if rate_limiter is not None and not rate_limiter.allow(api_key.key_id):
        raise HTTPException(
            status_code=429,
            detail={"error": {"type": "rate_limited", "message": "Too many requests. Slow down."}},
        )

    return AuthContext(user=user, role=role, api_key=api_key)


async def require_admin(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not ctx.role.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"error": {"type": "insufficient_privileges", "message": "Admin role required."}},
        )
    return ctx
