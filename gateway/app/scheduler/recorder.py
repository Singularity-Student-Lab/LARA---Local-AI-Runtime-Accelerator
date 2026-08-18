"""Records job-lifecycle transitions from within a StreamingResponse generator.

Why this exists: FastAPI's request-scoped `Depends(get_db)` session is closed by the
dependency's context manager as soon as the endpoint function returns - but a StreamingResponse
generator keeps running afterward, driven by the ASGI server as bytes are sent. Using the
request-scoped session from inside that generator would operate on an already-closed session.
JobRecorder opens its own short-lived session per update instead, looked up by request_id."""

from __future__ import annotations

import uuid

from app.db.models import Job
from app.db.session import SessionLocal
from app.scheduler import lifecycle

_TERMINAL = {"COMPLETED", "CANCELLED", "FAILED", "REJECTED"}


class JobRecorder:
    def __init__(self, request_id: uuid.UUID) -> None:
        self.request_id = request_id

    async def mark_running(self) -> None:
        async with SessionLocal() as db:
            job = await db.get(Job, self.request_id)
            if job is not None and job.status not in _TERMINAL:
                await lifecycle.mark_running(db, job)

    async def mark_completed(self, *, ttft_ms: int | None, input_tokens: int | None, output_tokens: int | None) -> None:
        async with SessionLocal() as db:
            job = await db.get(Job, self.request_id)
            if job is not None and job.status not in _TERMINAL:
                await lifecycle.mark_completed(
                    db, job, ttft_ms=ttft_ms, input_tokens=input_tokens, output_tokens=output_tokens
                )

    async def mark_failed(self, error_class: str) -> None:
        async with SessionLocal() as db:
            job = await db.get(Job, self.request_id)
            if job is not None and job.status not in _TERMINAL:
                await lifecycle.mark_failed(db, job, error_class)

    async def mark_cancelled(self, error_class: str) -> None:
        """First writer wins: if a /cancel endpoint already recorded a terminal state (e.g.
        error_class=user_cancel), a later disconnect-triggered call here must not clobber it
        with client_disconnect - see app/api/v1/chat.py's CancelledError handler."""
        async with SessionLocal() as db:
            job = await db.get(Job, self.request_id)
            if job is not None and job.status not in _TERMINAL:
                await lifecycle.mark_cancelled(db, job, error_class)
