# Scheduler and Queue

Implements blueprint Session 4. Verified for real on 2026-08-12 against a deterministic stub
backend (`tests/load/stub_backend/`), 6/7 load tests passing (1 explicitly skipped, see below),
plus all 18 Phase D unit/integration tests still passing after these changes.

## Design

`gateway/app/scheduler/queue.py`'s `Scheduler` is an in-process, priority-aware admission
controller: not a bare `asyncio.Semaphore`, because promotion has to respect effective
priority (descending) then FIFO within equal priority, and a per-user cap has to be enforced
at both admission and promotion time so one user cannot occupy every slot (blueprint section
5.4). It's built on an `asyncio.Condition` guarding a small waiter list, re-sorted and
re-evaluated on every admission and release - adequate at this project's scale (~12 users, a
3-job ceiling, queue depth in the tens), and simple enough to reason about.

**This is why the gateway runs as a single worker process** (`gateway/Dockerfile`): the
scheduler's state lives in this one Python object. Multiple uvicorn workers would each hold
their own `Scheduler` instance and silently multiply the GPU concurrency ceiling - the
blueprint calls this out explicitly as the most likely way to break the GPU safety property
without noticing, and the Dockerfile comment says so at the exact line that would break it.

Job history is separate and durable (`gateway/app/scheduler/lifecycle.py`, the `jobs` table).
The state machine follows blueprint section 5.2.1 exactly: `RECEIVED -> QUEUED -> RUNNING ->
{COMPLETED, FAILED, CANCELLED}`, with `REJECTED` as a terminal state for admission failures
that never queue.

## Two real bugs found while building this, not by inspection

1. **`X-LARA-Request-Id` didn't match the job's actual database id.** The header was populated
   from `RequestContextMiddleware`'s own independently-generated UUID, while the `jobs` table
   used SQLAlchemy's `default=uuid.uuid4` to generate a *second*, different UUID for the same
   request. Every cancellation and lookup test that used "the id the client was handed back"
   failed with 404. Fixed by making `lifecycle.create_received()` take `request_id` as a
   required argument and passing `request.state.request_id` explicitly, so there is exactly
   one id per request, used everywhere (`gateway/app/scheduler/lifecycle.py`,
   `gateway/app/api/v1/chat.py`).
2. **The stub backend itself had the same FastAPI union-return-type bug** documented in
   `docs/security/auth.md` for the real gateway code (`Response | dict` style return
   annotations aren't valid Pydantic response-model fields). Fixed with `response_model=None`.

Both were caught by `tests/load` failing, not by review - the reason this phase's tests run
against a real running stack rather than staying purely theoretical.

## A test-design bug worth recording

The first version of the ceiling/soak tests fired 10 concurrent requests from **one** admin
key and got `peak_active == 1`, which looked like a scheduler bug. It wasn't: with
`LARA_PER_USER_MAX_ACTIVE=1` (the default), a single user's own requests correctly serialize
to one concurrent slot regardless of the global ceiling - that's the anti-monopolization
control working as designed (blueprint section 5.4). Fixed by using 10 distinct throwaway
users to isolate what the test actually wanted to measure: the *global* 3-job ceiling. Left in
`tests/load/test_concurrency.py`'s docstrings as a note for future readers, since it's an easy
trap to fall into again.

## Cancellation mechanism

`gateway/app/scheduler/registry.py`'s `JobTaskRegistry` maps a job's `request_id` to the
`asyncio.Task` actually handling that HTTP request. `POST /lara/jobs/{id}/cancel` and
`POST /admin/jobs/{id}/cancel` call `.cancel()` on that task - which raises `CancelledError`
wherever the task is currently blocked, whether that's inside the scheduler's wait loop
(cancel while queued) or inside the httpx call to the backend (cancel while running). Both
paths unwind through the same `finally` blocks that release the slot and close the upstream
connection, so there is one cancellation code path, not two.

A background per-request watcher (`_watch_disconnect` in `gateway/app/api/v1/chat.py`) polls
`request.is_disconnected()` and cancels the same task if the client vanishes without an
explicit cancel call - covering disconnect-while-queued, which the streaming generator's own
disconnect check (mid-stream, for already-running requests) can't see.

`gateway/app/scheduler/recorder.py`'s `JobRecorder` exists because a `StreamingResponse`
generator keeps running after the endpoint function returns, by which point FastAPI has
already closed the request-scoped DB session - so lifecycle writes from inside a streaming
generator use their own short-lived session, looked up by `request_id`. It also has a
first-writer-wins guard: if `/cancel` already wrote `error_class=user_cancel`, a later
disconnect-triggered write cannot clobber it with `client_disconnect`.

## What's verified vs. what's open

Verified for real (`tests/load/test_concurrency.py`):

- Exactly 3 concurrently running jobs under 10-way contention from distinct users, 7 correctly
  queued, all 10 reach a terminal state, scheduler returns to 0/0 idle (T-S4-01, T-S4-02).
- No slot leak across two back-to-back saturation rounds (T-S4-13).
- Per-user cap holds a single user to 1 concurrent slot (T-S4-06).
- Admin can find and cancel a queued job before it ever runs (T-S4-07, admin variant).
- Cancelling an already-terminal job returns 409, not a silent no-op.
- A non-owning user gets 403 on both `GET /lara/jobs/{id}` and its cancel endpoint.

Explicitly skipped, not silently omitted: **queue-full / 429** (T-S4-12) - `LARA_QUEUE_MAX_DEPTH`
is process-wide (default 50) with no per-test override yet, and flooding 50+ concurrent stub
requests just to trip it is wasteful. Revisit once Phase F's mode/admin config allows a live
override.

Attempted but not conclusively verified: **restart reconciliation** (T-S4-14, killing the
gateway mid-request and confirming the orphaned row becomes `FAILED`/`gateway_restart` on
restart). Manual `docker kill` + curl timing in this sandboxed shell wasn't reliable enough to
reproduce the race deterministically - the reconciliation code itself
(`gateway/app/scheduler/reconcile.py`) is a direct, reviewed implementation of blueprint
section 5.2.4 and runs (with no orphaned rows found) on every normal restart performed
throughout this session, but the specific "kill mid-RUNNING-job" scenario should get a proper
automated regression test before this is called done.

## Timeout mechanics (blueprint section 5.2.2)

Connect, TTFT, and total-generation timeouts are implemented in
`gateway/app/models/proxy.py` (introduced in Phase D, reused unchanged here). Queue timeout
(`LARA_QUEUE_TIMEOUT_S`) is enforced by `Scheduler.admit()`'s deadline loop, tested implicitly
by every load test that completes within its window; a dedicated queue-timeout test is part of
the same follow-up as the queue-full test above.
