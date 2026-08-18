# Recovery Runbook

Implements blueprint section 15.5 / Session 7 point 9: kill each component, record what
clients see, whether recovery is automatic, how long it takes, and whether any job is left in
a bad state. Results below are real, run against the compose stack on this dev machine on
2026-08-12 - not projected.

## `lara-database` stopped

| What | Result |
| --- | --- |
| `GET /health` | Unaffected, stays `200` - deliberately does not depend on the database |
| Any authenticated endpoint | **Was a raw `500` with a full stack trace. Fixed** (see below) - now a clean `503 database_unavailable` |
| Recovery | `docker compose up -d lara-database`, gateway recovers automatically within ~5s once the DB is healthy again, no gateway restart needed (SQLAlchemy's connection pool just reconnects) |

**A real bug was found and fixed here, not simulated.** The gateway had no handler for
database connectivity failures, so FastAPI's default error path leaked an internal stack
trace as a `500` - violating blueprint section 16.4/20.3 (error bodies never contain internal
detail) and section 3's own Failure Modes table (which specifies `503`, fail closed). Two
exception types needed handling, discovered only by testing: `sqlalchemy.exc.DBAPIError` for
most driver-level failures, and a bare `socket.gaierror` (`OSError`) for the specific case of
Docker being unable to resolve the `lara-database` hostname while that container is stopped -
SQLAlchemy does not wrap that one in `DBAPIError` at all, since it fails before the driver's
own exception-translation layer runs. See `gateway/app/main.py`'s
`database_unavailable_handler` and the regression test in
`tests/unit/test_error_handling.py`.

## `lara-telemetry` stopped

| What | Result |
| --- | --- |
| Rest of the stack | Fully unaffected - no other service depends on it |
| Recovery | `docker compose up -d lara-telemetry`; resumes sampling immediately |

## `lara-gateway` killed mid-request (restart reconciliation)

See `docs/architecture/scheduler.md`: the reconciliation code
(`gateway/app/scheduler/reconcile.py`) runs on every boot and closes any orphaned
`QUEUED`/`RUNNING` job as `FAILED`/`gateway_restart` before serving traffic, per blueprint
section 5.2.4. This ran cleanly (0 orphaned rows) on every one of the many gateway restarts
performed throughout this development session. A deliberately-timed "kill exactly mid-request"
race was attempted but not reliably reproduced in this sandboxed shell environment - the
reconciliation code itself is a direct, reviewed implementation of the spec, but a proper
automated regression test for the exact race is still an open item (tracked, not silently
dropped).

## `docker kill` / `docker stop` vs. an actual in-process crash - a real, non-obvious finding

While testing recovery, `docker kill <container>` and an in-container `SIGKILL`/`SIGTERM` to
PID 1 were both observed to **not** trigger `restart: unless-stopped`, and
`RestartCount` stayed at `0`. Docker's daemon log explained why:
`"stopping restart-manager"` is logged at the moment of an explicit kill/stop - **Docker's
`unless-stopped` policy deliberately does not restart a container that was explicitly killed
or stopped**, by design (that's the literal meaning of "unless stopped": the policy restarts
after a crash, but an explicit stop is treated as the operator's intent, and is respected).

**Operational consequence, worth knowing before relying on this in production**: if an
operator (or a monitoring script) ever runs `docker kill`/`docker stop` on a LARA service
expecting `unless-stopped` to bring it back automatically, it will not - an explicit
`docker compose up -d <service>` (or `docker start`) is required. Genuine crash-recovery
(the process dying on its own from an unhandled exception, OOM-kill, or similar) is a
different code path and was not directly reproduced here due to sandboxed-environment signal
delivery not behaving as expected (see the git history of this file for the raw investigation
notes if needed) - this remains an open item to verify with an actual application-level crash
before considering Session 7's recovery testing fully closed.

## `lara-cloudflared`

Not tested - no live tunnel exists in this development context (`docs/operations/tunnel.md`).

## `lara-inference`

Not applicable - does not exist in this development context (`docs/operations/inference-runtime.md`).

## Full host reboot

Not tested - requires the beast (`docs/operations/host-setup-beast.md` section covering
reboot survival). On this dev machine, Docker's own restart-on-boot behavior for
`unless-stopped` containers is standard and was not separately re-verified as part of this
pass.

## Clean-machine deployment

Verified implicitly throughout this development session: every phase's `docker compose up -d
--build` ran migrations (`alembic upgrade head`) and seeding (`python -m database.seed.seed`)
automatically as part of `lara-gateway`'s startup command, with no manual step beyond `cp
.env.example .env` and filling in real values. A from-scratch clone-to-running verification
(blueprint Session 7 point 10.3) is still worth doing explicitly once - see
`docs/operations/exit-gates.md`.
