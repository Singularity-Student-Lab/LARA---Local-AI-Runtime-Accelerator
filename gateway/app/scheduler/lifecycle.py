"""Job row lifecycle (blueprint section 5.2, 21.6). The job row is created at RECEIVED before
admission, so rejections are countable, and every terminal transition records error_class from
the matrix in blueprint section 5.2.2."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job


def now() -> datetime:
    return datetime.now(timezone.utc)


def ms_between(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    return round((b - a).total_seconds() * 1000)


async def create_received(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    key_id: str,
    model_alias: str,
    backend_name: str,
    mode: str,
    effective_priority: int,
    stream: bool,
) -> Job:
    """`request_id` must be the same id already assigned to `request.state.request_id` by
    RequestContextMiddleware, not a freshly generated one - the X-LARA-Request-Id header
    returned to the client (blueprint section 20.3: "used for support, cancellation, and
    correlation") only works as a correlation id if it's the one thing everything agrees on.
    A real bug where these were two different UUIDs was caught by tests/load's cancellation
    tests: cancelling "the id the client was given" 404'd, because it wasn't the job's actual
    primary key."""
    job = Job(
        request_id=request_id,
        user_id=user_id,
        key_id=key_id,
        model_alias=model_alias,
        backend_name=backend_name,
        mode=mode,
        effective_priority=effective_priority,
        status="RECEIVED",
        stream=stream,
    )
    db.add(job)
    await db.commit()
    return job


async def mark_rejected(db: AsyncSession, job: Job, error_class: str) -> None:
    job.status = "REJECTED"
    job.error_class = error_class
    job.completed_at = now()
    await db.commit()


async def mark_queued(db: AsyncSession, job: Job) -> None:
    job.status = "QUEUED"
    job.queued_at = now()
    await db.commit()


async def mark_running(db: AsyncSession, job: Job) -> None:
    job.started_at = now()
    job.queue_wait_ms = ms_between(job.queued_at or job.received_at, job.started_at)
    job.status = "RUNNING"
    await db.commit()


async def mark_completed(
    db: AsyncSession, job: Job, *, ttft_ms: int | None, input_tokens: int | None, output_tokens: int | None
) -> None:
    job.completed_at = now()
    job.generation_ms = ms_between(job.started_at, job.completed_at)
    job.ttft_ms = ttft_ms
    job.input_tokens = input_tokens
    job.output_tokens = output_tokens
    job.status = "COMPLETED"
    await db.commit()


async def mark_failed(db: AsyncSession, job: Job, error_class: str) -> None:
    job.completed_at = now()
    if job.started_at is not None:
        job.generation_ms = ms_between(job.started_at, job.completed_at)
    job.status = "FAILED"
    job.error_class = error_class
    await db.commit()


async def mark_cancelled(db: AsyncSession, job: Job, error_class: str) -> None:
    job.completed_at = now()
    if job.started_at is not None:
        job.generation_ms = ms_between(job.started_at, job.completed_at)
    job.status = "CANCELLED"
    job.error_class = error_class
    await db.commit()
