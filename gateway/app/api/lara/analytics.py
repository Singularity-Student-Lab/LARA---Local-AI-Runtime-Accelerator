"""GET /lara/leaderboard, GET /lara/me (blueprint section 21.8 / Session 7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.analytics.leaderboard import compute_leaderboard, parse_weights
from app.api.errors import lara_error
from app.auth.dependencies import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.db.models import UsageDaily
from app.db.session import get_db

router = APIRouter()


@router.get("/lara/leaderboard")
async def get_leaderboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    if not settings.lara_leaderboard_enabled:
        raise lara_error(404, "leaderboard_disabled", "The leaderboard is disabled.", request)
    weights = parse_weights(settings.lara_leaderboard_weights)
    return await compute_leaderboard(db, weights)


@router.get("/lara/me")
async def get_my_usage(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> list[dict]:
    rows = (await db.execute(select(UsageDaily).where(UsageDaily.user_id == ctx.user.id))).scalars().all()
    return [
        {
            "day": r.day,
            "model_alias": r.model_alias,
            "requests": r.requests,
            "completed": r.completed,
            "failed": r.failed,
            "cancelled": r.cancelled,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "agent_sessions": r.agent_sessions,
        }
        for r in rows
    ]
