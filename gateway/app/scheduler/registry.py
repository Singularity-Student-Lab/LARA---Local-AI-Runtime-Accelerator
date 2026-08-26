"""Maps a job's request_id to the asyncio Task actually handling that HTTP request, so a
different request (POST /lara/jobs/{id}/cancel, POST /admin/jobs/{id}/cancel) can cancel it -
whether it is still waiting in the queue or already dispatched to the backend. Cancelling the
task makes whichever await it is currently blocked on raise CancelledError, which unwinds
through the scheduler's `finally` (releasing the slot) and the proxy's `finally`
(closing the upstream connection) - see app/scheduler/queue.py and app/models/proxy.py."""

from __future__ import annotations

import asyncio


class JobTaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def register(self, request_id: str, task: asyncio.Task) -> None:
        self._tasks[request_id] = task

    def unregister(self, request_id: str) -> None:
        self._tasks.pop(request_id, None)

    def get(self, request_id: str) -> asyncio.Task | None:
        return self._tasks.get(request_id)
