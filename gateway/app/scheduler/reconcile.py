"""Restart reconciliation (blueprint section 5.2.4). The scheduler is in-process; any job still
marked QUEUED or RUNNING from a previous process is closed as FAILED with
error_class=gateway_restart. Never attempt to resume - the client's HTTP connection is already
gone. Must run before the gateway accepts traffic, so active/queue counts start from truth."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.scheduler.lifecycle import now

logger = logging.getLogger("lara.gateway.scheduler")


async def reconcile_orphaned_jobs(db: AsyncSession) -> int:
    result = await db.execute(select(Job).where(Job.status.in_(["QUEUED", "RUNNING"])))
    orphaned = list(result.scalars().all())
    for job in orphaned:
        job.status = "FAILED"
        job.error_class = "gateway_restart"
        job.completed_at = now()
    if orphaned:
        await db.commit()
        logger.warning("reconciled orphaned jobs", extra={"count": len(orphaned)})
    return len(orphaned)
