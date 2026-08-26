# Storage Budget

Implements blueprint section 23.3 / PRD 12.1: worst case computed against a ~20GB total
operational budget (`LARA_LOG_MAX_GB`), verified against reality after a week of real
operation - not yet done, since this dev machine has run for hours, not a week. The arithmetic
below is the honest estimate; the "verify after a week" step is still open.

## Container logs (bounded, hard cap per service)

| Service | Cap | Notes |
| --- | --- | --- |
| `lara-gateway` | 50MB x 5 files = 250MB | `compose.yaml` `json-file` options |
| `lara-telemetry` | 20MB x 3 files = 60MB | |
| `lara-cloudflared` | 20MB x 3 files = 60MB | only when the `tunnel` profile runs |
| `lara-database` | Postgres default logging, not yet capped | **Open item**: add explicit `logging:` options once this matters in practice - not yet a problem at this scale |

Worst-case container-log total: **~370MB**, a small fraction of the 20GB budget.

## Database table growth (the actual budget driver)

Real row counts observed on this dev machine after several hours of development and testing
(2026-08-12): `jobs` ~200 rows, `gpu_samples` growing at 1 row per `LARA_GPU_SAMPLE_INTERVAL_S`
(5s default) = ~720 rows/hour = ~17,280 rows/day.

| Table | Retention | Rows/day (estimated from observed rate) | Row size (estimated) | Daily growth | At full retention window |
| --- | --- | --- | --- | --- | --- |
| `jobs` | 90 days (`LARA_RETENTION_JOBS_DAYS`) | Depends entirely on real usage volume - **not yet meaningfully estimable from dev testing traffic**, which is not representative of ~12 real users' agentic workloads | ~300 bytes | Unknown until real usage exists | Unknown |
| `gpu_samples` | 14 days raw (`LARA_RETENTION_GPU_RAW_DAYS`) | ~17,280 (fixed, driven by the sample interval, not usage) | ~150 bytes | ~2.6MB/day | ~36MB at 14 days |
| `gpu_samples_hourly` | long (aggregates) | 24 | ~150 bytes | ~3.6KB/day | Negligible over a year |
| `audit_events` | 365 days | Driven by admin actions, low volume | ~300 bytes + JSONB detail | Negligible at this scale (~12 users) | Low single-digit MB/year |
| `usage_daily` | long (aggregates) | (users x models) rows/day, small | ~200 bytes | Negligible | Negligible |

**Honest conclusion**: `gpu_samples` is the only table whose growth is predictable from this
dev session alone (fixed sampling rate), and it is nowhere near the 20GB budget even fully
retained for years. `jobs` growth is entirely usage-driven and cannot be honestly estimated
from dev-machine testing traffic, which used throwaway test users generating synthetic load,
not real agentic coding sessions. **This is exactly the kind of number the blueprint's own
rules forbid inventing** (section 0.3) - it stays open, to be measured for real once ~12 real
users generate real traffic (Session 7 / beast).

## Real table sizes, this instant (2026-08-12, several hours of dev+test traffic)

```
select relname, pg_size_pretty(pg_total_relation_size(relid)) as total_size, n_live_tup as row_estimate
from pg_stat_user_tables order by pg_total_relation_size(relid) desc;

      relname       | total_size | row_estimate
--------------------+------------+--------------
 audit_events       | 168 kB     |          275
 jobs               | 152 kB     |          126
 api_keys           | 104 kB     |          125
 gpu_samples        | 96 kB      |          256
 users              | 80 kB      |          124
 models             | 64 kB      |            8
 inference_backends | 48 kB      |            2
 roles              | 48 kB      |            5
 operating_mode     | 24 kB      |            1
 usage_daily        | 24 kB      |           32
 gpu_samples_hourly | 24 kB      |            0
 alembic_version    | 24 kB      |            1
```

Total database size right now: well under 1MB. This is dev-testing volume (many throwaway
users from `tests/load`/`tests/integration`), not representative of a week of real campus
usage - included as a real data point, not a projection.

## What to actually do once real usage exists

1. Run `scripts/retention.sh` on a schedule (see `docs/architecture/telemetry.md` - no cron
   exists in this repo, wire it to the host's own scheduler).
2. After one week of real operation, measure actual table sizes (`SELECT
   pg_size_pretty(pg_total_relation_size('jobs'));` etc.) and record them here, dated, replacing
   the estimates above with real numbers - per the blueprint's own rule that a result without
   its configuration and host state is not a result.
