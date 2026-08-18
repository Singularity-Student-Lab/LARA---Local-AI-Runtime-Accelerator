# Operating Modes and GPU Pressure

Implements blueprint Session 5. Verified for real on 2026-08-12: 7 mode/registry integration
tests + 8 pressure-evaluator unit tests, all passing (`tests/integration/test_modes.py`,
`tests/unit/test_pressure.py`).

## Mode policy is configuration, not branching logic

`gateway/app/modes/policy.py`'s `build_mode_policies()` returns a `dict[str, ModePolicy]` -
three data rows, not three `if mode == ...` branches. `gateway/app/modes/effective.py`
resolves the *current* mode row (`operating_mode` table) plus the *current* pressure level
into an `EffectivePolicy` fresh on every request, and applies it to the scheduler
(`Scheduler.max_active_jobs`, `Scheduler.per_user_max_active`) immediately before every
admission call. Mode and pressure are process-global, so this is safe under concurrency
without extra locking: concurrent requests recompute and write the same values.

**A real bug found here, not by inspection:** `GET /status` originally read
`scheduler.max_active_jobs` directly to report `effective_ceiling` - but that field is only
*updated* as a side effect of `chat.py`'s admission path running. Switching to `GAMEDEV` mode
and immediately calling `/status` with no chat traffic since reported the *previous* mode's
stale ceiling. Fixed by having `/status` call `compute_effective_policy()` independently,
decoupling reporting from mutation
(`tests/integration/test_modes.py::test_status_reflects_effective_ceiling_without_prior_traffic`
is the regression test).

## GPU pressure evaluator

`gateway/app/modes/pressure.py`'s `PressureEvaluator` applies two filters in sequence, exactly
as the blueprint specifies (section 5.3.3 points 1-5):

1. **Rolling median**, not the latest sample, over a configurable window - so one spike frame
   cannot pause the service.
2. **Hysteresis** - a candidate level has to repeat for `hysteresis_samples` consecutive
   evaluations before it actually becomes the current level, so noise near a threshold
   doesn't flap the system between levels.

Getting this right required real debugging, documented in `tests/unit/test_pressure.py`: the
first draft of the hysteresis test asserted a transition after a single elevated sample,
which is wrong once median smoothing is in the loop - a 5-sample window needs several
consistently-elevated samples before the *median* even crosses the threshold, and only then
does the hysteresis counter start. The fixed tests isolate each filter (a 1-sample window
tests hysteresis alone; a fully-saturated window tests the interaction of both).

**Fail-safe behavior, verified for real, not simulated:** this dev container has no GPU
passthrough (`docs/operations/dev-environment.md` - the NVIDIA Container Toolkit is not
configured on this machine), so every `nvidia-smi` sampling attempt genuinely fails. The
evaluator's fail-safe path (`ingest(None)` -> escalate to `MODERATE`, never stay `LOW`,
`telemetry_healthy=False`, log a warning) runs on every startup and is visible in the gateway
logs (`"telemetry unavailable, failing safe to MODERATE pressure"`). This is exactly the
condition blueprint section 5.3.3's failure table calls out, exercised by circumstance rather
than by a mock.

Full NVML-based sampling into a persistent `gpu_samples` table (retention, aggregation, a real
sampler container) is Phase H (Session 7) - this evaluator is the "prototype form" the
blueprint's Session 5 prerequisites explicitly allow.

## Owner priority bonus

`PERSONAL` mode's `owner_priority_bonus` (seeded at 1000) is added to `effective_priority`
only when the requesting user's role is named `owner` (`ctx.role.name == "owner"`), matching
the blueprint's seeded role set. "Owner unlimited up to the ceiling" (section 5.3.2) is
approximated as a large `per_user_max_active` for `PERSONAL` mode rather than a true per-role
override, since the scheduler's per-user cap is a single process-wide value - documented in
`gateway/app/modes/policy.py` as a deliberate, recorded simplification, not a silent gap.

## What is genuinely deferred

- Real production pressure thresholds: `NOT YET MEASURED`, seeded with dev-GPU-appropriate
  provisional values in `.env.example`, explicitly marked invalid for the production RTX 5060
  Ti 16GB.
- Validation against a real Unity/Unreal workload: requires the beast (Session 7).
- `scripts/model.sh`'s drain/recreate/rollback steps: only meaningful once a real vLLM
  container exists to switch between profiles - see `docs/operations/model-switch.md`.
