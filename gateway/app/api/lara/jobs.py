"""GET /lara/queue, GET /lara/jobs/{id}, POST /lara/jobs/{id}/cancel (blueprint section 4,
Session 4 point 7). A user sees only their own queue position and jobs, never other users'
identities or details (Engineering Recommendation, section 4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.errors import lara_error
from app.auth.dependencies import AuthContext, get_auth_context
from app.db.models import Job
from app.db.session import get_db
from app.scheduler.lifecycle import mark_cancelled

router = APIRouter()

CANCELLABLE = {"RECEIVED", "QUEUED", "RUNNING"}


def job_out(job: Job) -> dict:
    return {
        "request_id": str(job.request_id),
        "status": job.status,
        "model_alias": job.model_alias,
        "stream": job.stream,
        "received_at": job.received_at.isoformat() if job.received_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "queue_wait_ms": job.queue_wait_ms,
        "generation_ms": job.generation_ms,
        "ttft_ms": job.ttft_ms,
        "input_tokens": job.input_tokens,
        "output_tokens": job.output_tokens,
        "error_class": job.error_class,
    }


@router.get("/lara/queue")
async def get_queue(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict:
    scheduler = request.app.state.scheduler
    return scheduler.snapshot_for(str(ctx.user.id))


@router.get("/lara/jobs/{request_id}")
async def get_job(
    request: Request,
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> dict:
    job = (await db.execute(select(Job).where(Job.request_id == request_id))).scalar_one_or_none()
    if job is None:
        raise lara_error(404, "job_not_found", "Unknown job.", request)
    if job.user_id != ctx.user.id:
        raise lara_error(403, "not_job_owner", "This job belongs to another user.", request)
    return job_out(job)


@router.post("/lara/jobs/{request_id}/cancel")
async def cancel_own_job(
    request: Request,
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> dict:
    job = (await db.execute(select(Job).where(Job.request_id == request_id))).scalar_one_or_none()
    if job is None:
        raise lara_error(404, "job_not_found", "Unknown job.", request)
    if job.user_id != ctx.user.id:
        raise lara_error(403, "not_job_owner", "This job belongs to another user.", request)
    if job.status not in CANCELLABLE:
        raise lara_error(409, "job_already_terminal", f"Job is already {job.status}.", request)

    await mark_cancelled(db, job, "user_cancel")

    task_registry = request.app.state.job_tasks
    task = task_registry.get(str(request_id))
    if task is not None:
        task.cancel()

    return job_out(job)
