"""Current operating mode: a single DB row, changed only through set_mode() so every
transition is audited with actor, previous mode, new mode, and timestamp (blueprint section
5.3.1 point 1 / PRD 8.4). Mode changes never kill running jobs (PRD 8.2) - set_mode only
changes what admission consults next; it does not touch the scheduler or any in-flight job."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent, OperatingMode
from app.modes.policy import MODES
from app.scheduler.lifecycle import now


class UnknownModeError(Exception):
    pass


async def get_or_create_mode_row(db: AsyncSession) -> OperatingMode:
    row = (await db.execute(select(OperatingMode).where(OperatingMode.id == 1))).scalar_one_or_none()
    if row is None:
        row = OperatingMode(id=1, mode="SERVING", switching=False)
        db.add(row)
        await db.commit()
    return row


async def set_mode(db: AsyncSession, *, new_mode: str, actor_user_id: uuid.UUID) -> OperatingMode:
    if new_mode not in MODES:
        raise UnknownModeError(new_mode)
    row = await get_or_create_mode_row(db)
    previous = row.mode
    row.mode = new_mode
    row.changed_by = actor_user_id
    row.changed_at = now()
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            event_type="mode.change",
            target=new_mode,
            detail={"previous_mode": previous, "new_mode": new_mode},
        )
    )
    await db.commit()
    return row
