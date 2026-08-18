"""In-process priority-aware admission controller (blueprint section 4, Session 4).

ENGINEERING RECOMMENDATION carried from the blueprint: one process, in-memory scheduler,
durable job records. The scheduler state (slots and the waiting set) lives here, in the
gateway process; job history lives in PostgreSQL (app/scheduler/lifecycle.py). This is why the
gateway MUST run as a single worker process (see gateway/Dockerfile) - multiple workers would
each hold their own instance of this class and silently multiply the GPU concurrency ceiling.

Not a bare asyncio.Semaphore: promotion has to respect priority (descending) then FIFO within
equal priority (blueprint section 5.4), and a per-user cap that must be checked at both
admission and promotion time so one user cannot hold every slot (section 5.2 point 3).
"""

from __future__ import annotations

import asyncio
import dataclasses
import itertools
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.scheduler.errors import QueueFullError, QueueTimeoutError

_seq_counter = itertools.count()


@dataclasses.dataclass
class _Waiter:
    priority: int
    seq: int
    user_id: str
    promoted: bool = False


class Scheduler:
    def __init__(self, max_active_jobs: int, per_user_max_active: int, queue_max_depth: int) -> None:
        self.max_active_jobs = max_active_jobs
        self.per_user_max_active = per_user_max_active
        self.queue_max_depth = queue_max_depth

        self._active_count = 0
        self._active_by_user: dict[str, int] = defaultdict(int)
        self._waiting: list[_Waiter] = []
        self._cond = asyncio.Condition()

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def queue_depth(self) -> int:
        return len(self._waiting)

    def snapshot_for(self, user_id: str) -> dict:
        """Non-blocking read for /lara/queue - a user sees only their own waiting jobs and
        never other users' identities (blueprint section 4, Session 4 point 7 recommendation)."""
        own_waiting = sum(1 for w in self._waiting if w.user_id == user_id)
        return {
            "active_count": self._active_count,
            "queue_depth": len(self._waiting),
            "effective_ceiling": self.max_active_jobs,
            "your_queued_jobs": own_waiting,
        }

    def _try_promote_locked(self) -> None:
        self._waiting.sort(key=lambda w: (-w.priority, w.seq))
        for w in list(self._waiting):
            if self._active_count >= self.max_active_jobs:
                break
            if self._active_by_user[w.user_id] >= self.per_user_max_active:
                continue
            w.promoted = True
            self._waiting.remove(w)
            self._active_count += 1
            self._active_by_user[w.user_id] += 1

    @asynccontextmanager
    async def admit(self, *, user_id: str, effective_priority: int, queue_timeout_s: float) -> AsyncIterator[None]:
        """Blocks until a slot is granted, then yields. Releases the slot on exit (success,
        exception, or cancellation - e.g. client disconnect while queued)."""
        waiter = _Waiter(priority=effective_priority, seq=next(_seq_counter), user_id=user_id)

        async with self._cond:
            if len(self._waiting) >= self.queue_max_depth:
                raise QueueFullError()
            self._waiting.append(waiter)
            self._try_promote_locked()
            self._cond.notify_all()

        try:
            deadline = time.monotonic() + queue_timeout_s
            async with self._cond:
                while not waiter.promoted:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        if waiter in self._waiting:
                            self._waiting.remove(waiter)
                        raise QueueTimeoutError()
                    try:
                        await asyncio.wait_for(self._cond.wait(), timeout=remaining)
                    except asyncio.TimeoutError:
                        pass  # loop re-checks the deadline and promotion state
        except asyncio.CancelledError:
            async with self._cond:
                if waiter in self._waiting:
                    self._waiting.remove(waiter)
                    self._try_promote_locked()
                    self._cond.notify_all()
            raise

        try:
            yield
        finally:
            async with self._cond:
                self._active_count -= 1
                self._active_by_user[waiter.user_id] -= 1
                if self._active_by_user[waiter.user_id] <= 0:
                    del self._active_by_user[waiter.user_id]
                self._try_promote_locked()
                self._cond.notify_all()
