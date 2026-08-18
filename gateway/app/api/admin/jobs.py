"""GET /admin/jobs, POST /admin/jobs/{id}/cancel (blueprint section 4, Session 4 point 7)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.errors import lara_error
from app.api.lara.jobs import CANCELLABLE, job_out
from app.auth.dependencies import AuthContext, require_admin
from app.db.models import AuditEvent, Job
from app.db.session import get_db
from app.scheduler.lifecycle import mark_cancelled

router = APIRouter()


@router.get("/admin/jobs")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
    status: str | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    model_alias: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[dict]:
    stmt = select(Job).order_by(Job.received_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(Job.status == status)
    if user_id is not None:
        stmt = stmt.where(Job.user_id == user_id)
    if model_alias is not None:
        stmt = stmt.where(Job.model_alias == model_alias)
    result = await db.execute(stmt)
    return [{**job_out(job), "user_id": str(job.user_id)} for job in result.scalars().all()]


@router.post("/admin/jobs/{request_id}/cancel")
async def admin_cancel_job(
    request: Request,
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    job = (await db.execute(select(Job).where(Job.request_id == request_id))).scalar_one_or_none()
    if job is None:
        raise lara_error(404, "job_not_found", "Unknown job.", request)
    if job.status not in CANCELLABLE:
        raise lara_error(409, "job_already_terminal", f"Job is already {job.status}.", request)

    await mark_cancelled(db, job, "admin_cancel")
    db.add(
        AuditEvent(
            actor_user_id=ctx.user.id,
            event_type="job.admin_cancel",
            target=str(request_id),
            detail={"previous_status": job.status},
        )
    )
    await db.commit()

    task_registry = request.app.state.job_tasks
    task = task_registry.get(str(request_id))
    if task is not None:
        task.cancel()

    return {**job_out(job), "user_id": str(job.user_id)}
