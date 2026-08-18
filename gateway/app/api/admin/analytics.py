"""GET /admin/metrics, GET /admin/analytics, POST /admin/analytics/rollup (blueprint section
21.7-21.8 / Session 7 points 2-3). Administrative, never public - detailed per-user analytics
would leak individual work patterns if exposed generally (blueprint section 7 Security
Considerations point 3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.analytics.rollup import rollup_day
from app.auth.dependencies import AuthContext, require_admin
from app.db.models import GpuSample, Job, UsageDaily
from app.db.session import get_db
from app.modes.state import get_or_create_mode_row

router = APIRouter()


class RollupRequest(BaseModel):
    day: str | None = None  # ISO date, defaults to today (UTC)


@router.get("/admin/metrics")
async def get_metrics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    scheduler = request.app.state.scheduler
    pressure = request.app.state.pressure_evaluator
    mode_row = await get_or_create_mode_row(db)

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = (await db.execute(select(Job).where(Job.received_at >= since))).scalars().all()

    ttfts = [j.ttft_ms for j in recent if j.ttft_ms is not None]
    tokens_per_s = [
        (j.output_tokens / (j.generation_ms / 1000))
        for j in recent
        if j.output_tokens and j.generation_ms and j.generation_ms > 0
    ]
    error_counts: dict[str, int] = {}
    for j in recent:
        if j.error_class:
            error_counts[j.error_class] = error_counts.get(j.error_class, 0) + 1

    last_sample = (
        await db.execute(select(GpuSample).order_by(GpuSample.sampled_at.desc()).limit(1))
    ).scalar_one_or_none()

    return {
        "active_jobs": scheduler.active_count,
        "queue_depth": scheduler.queue_depth,
        "effective_ceiling": scheduler.max_active_jobs,
        "mode": mode_row.mode,
        "pressure_level": pressure.current_level,
        "telemetry_healthy": last_sample.telemetry_healthy if last_sample else None,
        "last_gpu_sample_at": last_sample.sampled_at.isoformat() if last_sample else None,
        "recent_1h": {
            "requests": len(recent),
            "ttft_ms_mean": round(sum(ttfts) / len(ttfts)) if ttfts else None,
            "tokens_per_s_mean": round(sum(tokens_per_s) / len(tokens_per_s), 2) if tokens_per_s else None,
            "error_counts": error_counts,
        },
    }


@router.get("/admin/analytics")
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
    day: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
) -> list[dict]:
    stmt = select(UsageDaily)
    if day is not None:
        stmt = stmt.where(UsageDaily.day == day)
    if user_id is not None:
        stmt = stmt.where(UsageDaily.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "day": r.day,
            "user_id": str(r.user_id),
            "model_alias": r.model_alias,
            "requests": r.requests,
            "completed": r.completed,
            "failed": r.failed,
            "cancelled": r.cancelled,
            "rejected": r.rejected,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "generation_ms_total": r.generation_ms_total,
            "queue_wait_ms_mean": r.queue_wait_ms_mean,
            "queue_wait_ms_p95": r.queue_wait_ms_p95,
            "ttft_ms_mean": r.ttft_ms_mean,
            "ttft_ms_p95": r.ttft_ms_p95,
            "agent_sessions": r.agent_sessions,
        }
        for r in rows
    ]


@router.post("/admin/analytics/rollup")
async def post_rollup(
    body: RollupRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    target_day = date.fromisoformat(body.day) if body.day else datetime.now(timezone.utc).date()
    groups = await rollup_day(db, target_day)
    return {"day": target_day.isoformat(), "groups_rolled_up": groups}
