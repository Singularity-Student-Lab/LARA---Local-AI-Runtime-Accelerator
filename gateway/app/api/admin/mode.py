"""GET/POST /admin/mode (blueprint section 5.3.1 point 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.errors import lara_error
from app.auth.dependencies import AuthContext, require_admin
from app.db.session import get_db
from app.modes.policy import MODES
from app.modes.state import UnknownModeError, get_or_create_mode_row, set_mode

router = APIRouter()


class SetModeRequest(BaseModel):
    mode: str


@router.get("/admin/mode")
async def get_mode(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    row = await get_or_create_mode_row(db)
    policy = request.app.state.mode_policies[row.mode]
    return {
        "mode": row.mode,
        "changed_at": row.changed_at.isoformat() if row.changed_at else None,
        "switching": row.switching,
        "policy": {
            "max_active_jobs": policy.max_active_jobs,
            "per_user_max_active": policy.per_user_max_active,
            "owner_priority_bonus": policy.owner_priority_bonus,
            "pressure_policy_enabled": policy.pressure_policy_enabled,
        },
        "pressure_level": request.app.state.pressure_evaluator.current_level,
        "telemetry_healthy": request.app.state.pressure_evaluator.telemetry_healthy,
    }


@router.post("/admin/mode")
async def post_mode(
    request: Request,
    body: SetModeRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    if body.mode not in MODES:
        raise lara_error(400, "unknown_mode", f"Unknown mode '{body.mode}'. Valid: {list(MODES)}", request)
    row = await set_mode(db, new_mode=body.mode, actor_user_id=ctx.user.id)
    return {"mode": row.mode, "changed_at": row.changed_at.isoformat()}
