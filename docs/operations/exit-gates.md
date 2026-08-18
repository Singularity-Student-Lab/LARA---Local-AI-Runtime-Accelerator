# Exit Gates — Dev-PC-First Implementation

Tracks the adapted-session exit gates from the plan this repo followed
(`Docs/LARA_7_Session_Implementation_Reference.md` Sessions 1-7, adapted for dev-PC-first
implementation per the user's directive). Every gate below is either **CLOSED**, with real
evidence cited, or **OPEN**, with what's blocking it stated honestly - nothing is marked closed
without something in this repo to point at.

## Adapted Session 1 (Phase A) — CLOSED for the dev machine, OPEN for the beast

- [x] Repo skeleton, `.gitignore`, `.env.example`, `compose.yaml` committed.
- [x] Dev environment recorded from real discovery: `docs/operations/dev-environment.md`.
- [x] Idle baseline recorded (dev machine, dated): `docs/benchmarks/baseline-idle.md` section 1.
- [x] `scripts/health.sh` runs and reports per-layer pass/fail.
- [ ] **Beast GPU chain (Windows -> WSL2 -> Docker -> CUDA -> RTX 5060 Ti)**: OPEN. No such
      hardware exists in this context. Runbook ready: `docs/operations/host-setup-beast.md`.

## Adapted Session 2 (Phase B) — Dev path CLOSED, production path formally blocked

- [x] Ollama dev backend endpoint matrix verified for real: `docs/operations/dev-backend.md`.
- [x] `inference/scripts/smoke.sh` passes against the dev backend.
- [x] Container-to-host reachability resolved and verified for this machine (with the user's
      explicit approval for the `OLLAMA_HOST=0.0.0.0` systemd override).
- [ ] **Production vLLM path**: formally blocked, documented bypass in effect per blueprint
      section 4.3 rule 4 - `docs/operations/inference-runtime.md`.

## Adapted Session 3 (Phase C+D) — CLOSED

- [x] `client -> authenticated lara-gateway -> backend` works end to end, verified with real
      curl traffic and a bootstrap-issued key.
- [x] `lara-database` and (once it exists) `lara-inference` unreachable from outside Docker -
      verified via `docker compose ps` Publishers (no ports: entry).
- [x] Every T-S3-xx auth case passes: 9 automated tests in `tests/integration/test_auth.py`,
      all real HTTP traffic against the running stack, not mocked.
- [x] Migrations run from empty and seed correctly - proven three separate times (initial
      schema, jobs table, operating_mode table, gpu_samples/usage_daily), each with a real
      upgrade/downgrade/re-upgrade round trip against Postgres.
- [x] Audit events recorded for admin actions.
- [x] A real bug (key-parsing collision on `_`) was found by testing and fixed -
      `docs/security/auth.md`.

## Adapted Session 4 (Phase E) — CLOSED, one item open

- [x] 3 running / N queued proven with distinct users against a deterministic stub backend -
      `tests/load/test_concurrency.py`, 6/7 passing.
- [x] Priority, per-user cap, cancellation (queued and running, owner and admin), ownership
      enforcement (403/404/409) all verified with real HTTP traffic.
- [x] No slot leak across repeated saturation rounds.
- [x] A real bug (X-LARA-Request-Id not matching the job's actual database id) was found and
      fixed.
- [ ] **Queue-full (429) test**: explicitly skipped, not silently omitted - see
      `docs/architecture/scheduler.md`.
- [ ] **Restart-mid-request reconciliation**: reconciliation code is a direct, reviewed
      implementation of the spec and runs cleanly on every normal restart, but the specific
      timed race was not conclusively reproduced in this sandboxed shell - open item.

## Adapted Session 5 (Phase F) — CLOSED for logic, OPEN for real-hardware tuning

- [x] Three modes implemented, persisted, audited - `tests/integration/test_modes.py`.
- [x] GPU pressure evaluator: median smoothing + hysteresis, unit-tested (8 tests), and its
      fail-safe path (telemetry loss -> MODERATE) verified for real on this GPU-passthrough-less
      container, not simulated.
- [x] A real bug (`/status` reporting a stale effective ceiling) was found and fixed.
- [x] Model registry CRUD, alias resolution, disabled-alias rejection - all verified.
- [x] `scripts/mode.sh` and `scripts/model.sh` both run for real against this stack (the latter
      hit a genuine bash quoting bug in `${VAR:?message}` with an apostrophe, found and fixed).
- [ ] **Real production pressure thresholds, validated against a real game workload**: OPEN,
      requires the beast - `docs/operations/gamedev.md`.

## Adapted Session 6 (Phase G) — CLOSED locally, OPEN for live external access

- [x] `lara-cloudflared` service defined, network-isolated to `lara_edge` only, never started
      by default.
- [x] `scripts/audit-ports.sh` passes - and its own methodology was corrected mid-development
      after a real false positive (an unrelated native PostgreSQL service on this dev machine)
      - `docs/security/exposure.md`.
- [x] Rate limiting and auth-fail throttling implemented and verified for real - the throttle
      was genuinely tripped by this session's own cumulative testing traffic and correctly
      blocked a subsequently-valid key from the same source.
- [ ] **T-S6-01 through T-S6-06, T-S6-15 (live tunnel, three networks, external agent)**: OPEN,
      no Cloudflare account exists in this context - `docs/operations/tunnel.md`.

## Adapted Session 7 (Phase H) — Scaffolding and dev-scale verification CLOSED, production benchmarks OPEN

- [x] `lara-telemetry` running, writing real rows into `gpu_samples` on this machine.
- [x] Full analytics pipeline (`jobs -> rollup -> usage_daily -> leaderboard/metrics/analytics`)
      exercised end to end with real job data.
- [x] A real bug (database outage surfacing as a raw `500` instead of the spec's `503`, across
      two different exception types) was found and fixed, with a regression test.
- [x] Storage budget documented with real current table sizes, honest about what can and
      cannot be estimated from dev-scale traffic.
- [x] Recovery runbook: `lara-database` and `lara-telemetry` outage/recovery verified for real;
      a genuinely useful, non-obvious finding recorded about `docker kill`/`stop` vs.
      `unless-stopped` semantics.
- [ ] **Production concurrency benchmarks, agentic benchmark, model selection**: OPEN, all
      explicitly `PENDING` in `docs/benchmarks/`, nothing fabricated.

## What "done" means right now

Everything that can be built and proven without the RTX 5060 Ti 16GB / Windows-WSL2 beast has
been built and proven with real, repeatable evidence - not just written and assumed to work.
`tests/unit` + `tests/integration` (42 tests) and `tests/load` (6/7, one deliberately skipped)
all pass against the live stack on this machine as of 2026-08-12. Six real bugs were found by
testing throughout this implementation, not by inspection, and are documented where they were
fixed rather than only listed here:

1. API key parsing broke on keys containing `_` (Phase D).
2. `X-LARA-Request-Id` didn't match the job's actual database id (Phase E).
3. A test-design bug (not a scheduler bug) misread per-user cap enforcement as a concurrency
   failure (Phase E).
4. A FastAPI union-return-type bug in the test stub backend (Phase E).
5. A bash `${VAR:?message}` quoting bug with an apostrophe in the message text (Phase F).
6. Database-outage handling leaked a raw `500` instead of the spec's `503`, across two
   different exception types (Phase H).

What remains is genuinely beast-bound: real GPU chain verification, production vLLM,
production benchmarks, live external tunnel access, and the final model selection. Nothing in
this list can be closed without that hardware, and nothing here pretends otherwise.
