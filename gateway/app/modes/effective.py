"""Resolves the mode+pressure global state into the values admission actually consults,
applied to the scheduler right before each admit() call (blueprint section 5.3.1 point 3:
"Admission consults the active mode for: effective max_active_jobs, per_user_max_active,
context and output caps, priority bonuses, and whether the pressure policy is active").

Mode and pressure are process-global, not per-request, so concurrent requests writing the
same computed values to the scheduler's plain attributes is benign - see the module docstring
discussion in gateway/app/api/v1/chat.py history for why no lock is needed here."""

from __future__ import annotations

import dataclasses

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.modes.policy import pressure_adjusted_ceiling
from app.modes.state import get_or_create_mode_row


@dataclasses.dataclass(frozen=True)
class EffectivePolicy:
    mode: str
    ceiling: int
    per_user_max_active: int
    priority_bonus: int
    pressure_level: str


async def compute_effective_policy(request: Request, db: AsyncSession, *, is_owner: bool) -> EffectivePolicy:
    settings = request.app.state.settings
    mode_row = await get_or_create_mode_row(db)
    policy = request.app.state.mode_policies[mode_row.mode]

    pressure_level = "LOW"
    if policy.pressure_policy_enabled:
        pressure_level = request.app.state.pressure_evaluator.current_level

    ceiling = min(settings.lara_max_active_jobs, policy.max_active_jobs)
    if policy.pressure_policy_enabled:
        ceiling = pressure_adjusted_ceiling(ceiling, pressure_level)

    bonus = policy.owner_priority_bonus if is_owner else 0

    return EffectivePolicy(
        mode=mode_row.mode,
        ceiling=ceiling,
        per_user_max_active=policy.per_user_max_active,
        priority_bonus=bonus,
        pressure_level=pressure_level,
    )


def apply_to_scheduler(request: Request, effective: EffectivePolicy) -> None:
    scheduler = request.app.state.scheduler
    scheduler.max_active_jobs = effective.ceiling
    scheduler.per_user_max_active = effective.per_user_max_active
