"""GET /status - authenticated, operational state (blueprint section 3, Session 3 point 8;
extended in Phase F with mode/pressure per section 5.3.1, and Phase E with live queue state)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.dependencies import AuthContext, get_auth_context
from app.db.session import get_db
from app.models.registry import get_default_alias, resolve_alias
from app.modes.effective import compute_effective_policy
from app.modes.state import get_or_create_mode_row

router = APIRouter()


@router.get("/status")
async def status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> dict:
    default_row = await get_default_alias(db)

    backend_healthy: bool | None = None
    if default_row is not None:
        resolved = await resolve_alias(db, default_row.alias)
        if resolved is not None:
            client: httpx.AsyncClient = request.app.state.backend_client
            try:
                resp = await client.get(f"{resolved.backend.base_url.rstrip('/')}/v1/models", timeout=3.0)
                backend_healthy = resp.status_code < 500
            except httpx.HTTPError:
                backend_healthy = False

    mode_row = await get_or_create_mode_row(db)
    scheduler = request.app.state.scheduler
    pressure = request.app.state.pressure_evaluator

    # Computed independently of chat.py's admission path (never read scheduler.max_active_jobs
    # directly here) - that value is only a side effect of the last request that happened to
    # run, and would report stale data immediately after a mode/pressure change with no
    # traffic since. This mirrors exactly what the NEXT admission would compute.
    effective = await compute_effective_policy(request, db, is_owner=(ctx.role.name == "owner"))

    return {
        "active_model_alias": default_row.alias if default_row else None,
        "backend_healthy": backend_healthy,
        "mode": mode_row.mode,
        "pressure_level": pressure.current_level,
        "active_jobs": scheduler.active_count,
        "queue_depth": scheduler.queue_depth,
        "effective_ceiling": effective.ceiling,
        "telemetry_healthy": pressure.telemetry_healthy,  # placeholder - full telemetry sampler lands in Phase H
        "switching": mode_row.switching,
    }
