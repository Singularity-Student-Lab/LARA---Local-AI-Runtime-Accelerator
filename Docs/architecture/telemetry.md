# Telemetry and Analytics

Implements blueprint section 21.7-21.8 / Session 7. Verified for real on 2026-08-12: the
`lara-telemetry` container is running on this dev machine, writing real rows into
`gpu_samples` every `LARA_GPU_SAMPLE_INTERVAL_S`; the full analytics pipeline (jobs -> rollup
-> `usage_daily` -> leaderboard/metrics/analytics endpoints) was exercised end to end with
real job data generated via the deterministic stub backend (`tests/load/stub_backend/`).

## Collector

`monitoring/collector/main.py` reuses `app.modes.pressure.sample_gpu()` - one NVML/nvidia-smi
sampling implementation, used by both the live in-gateway pressure evaluator (Phase F) and
this durable collector, rather than two copies that could drift. On this dev container (no
GPU passthrough - see `docs/operations/dev-environment.md`), every GPU sample is `None` and
`telemetry_healthy=false` is correctly recorded on every row - the real database contains
proof that the fail-safe path was exercised, not simulated.

CPU/RAM are read from `/proc/loadavg` and `/proc/meminfo` inside the collector container.
**This is the collector container's view**, not necessarily identical to a true bare-metal
reading - the same caveat pattern the blueprint itself uses for WSL2-vs-Windows (Session 7
point 2), applied here to container-vs-host. Verified real values were captured (~30-35% CPU
load average, ~7.7GB RAM used) matching this machine's actual state at the time.

**Deliberate adaptation from the blueprint's compose skeleton**: `lara-telemetry` runs under
both `dev` and `prod` profiles, not `prod` only, because validating the pressure evaluator and
the retention pipeline meaningfully needs real samples on this development machine (recorded
in the plan this repo followed, and in `docs/operations/dev-environment.md`).

## Analytics pipeline

`gateway/app/analytics/rollup.py`'s `rollup_day()` aggregates `jobs` into `usage_daily` per
`(user, day, model_alias)` - idempotent (clears and recomputes that day's rows), triggered
manually via `POST /admin/analytics/rollup` today. **No cron scheduler exists in this
codebase** (deliberate, matching PRD 1.3 principle 13 "do not over-engineer for hypothetical
scale") - `scripts/retention.sh` and the rollup endpoint are meant to be invoked by the host's
own scheduler (systemd timer, cron, or Windows Task Scheduler on the eventual beast), not by
application code inventing its own job-scheduling system for two recurring tasks.

## Leaderboard anti-gaming, verified against real accumulated test data

`gateway/app/analytics/leaderboard.py` implements the blueprint's scoring components exactly
(successful requests via `sqrt`-diminished daily counts, distinct active days, agent sessions,
small token weight). Running it against this session's real accumulated job history (dozens of
throwaway test users from `tests/load` and `tests/integration` runs) produced a plausible,
non-token-dominated ranking - see the raw output preserved in this document's git history if
needed, not reproduced here since it is throwaway test data, not a meaningful leaderboard.

## What's genuinely deferred to Session 7 on the beast

- Real NVML power draw (`power_w` is always null today - `sample_gpu()` does not parse it;
  **UNKNOWN - MUST BE VERIFIED** whether the pinned nvidia-smi query reports it on the
  production card).
- `active_jobs`/`queue_depth` columns on `gpu_samples` are always null from the standalone
  collector (it has no reachable gateway process to ask) - only meaningful once the collector
  and gateway share a way to correlate, which the blueprint leaves as a Session 7 detail.
- Real production benchmarks and the leaderboard's actual first meaningful season - see
  `docs/benchmarks/`.
