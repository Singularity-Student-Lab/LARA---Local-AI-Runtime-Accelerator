"""Retention: bounds the fastest-growing tables so the service never fills the disk because
logging was forgotten (PRD 12.1, 12.5). A deletion path is a data-loss event if wrong - tested
here against a real database, never run untested against production data (blueprint section
7 Security Considerations point 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent, GpuSample, Job


async def apply_retention(
    db: AsyncSession, *, jobs_days: int, gpu_raw_days: int, audit_days: int
) -> dict[str, int]:
    now = datetime.now(timezone.utc)

    jobs_cutoff = now - timedelta(days=jobs_days)
    gpu_cutoff = now - timedelta(days=gpu_raw_days)
    audit_cutoff = now - timedelta(days=audit_days)

    jobs_result = await db.execute(delete(Job).where(Job.received_at < jobs_cutoff))
    gpu_result = await db.execute(delete(GpuSample).where(GpuSample.sampled_at < gpu_cutoff))
    audit_result = await db.execute(delete(AuditEvent).where(AuditEvent.occurred_at < audit_cutoff))

    await db.commit()

    return {
        "jobs_deleted": jobs_result.rowcount or 0,
        "gpu_samples_deleted": gpu_result.rowcount or 0,
        "audit_events_deleted": audit_result.rowcount or 0,
    }
