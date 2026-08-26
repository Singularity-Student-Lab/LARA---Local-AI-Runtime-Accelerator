# Model Switch Runbook

Implements blueprint section 22.4 / diagram 10. `scripts/model.sh` automates the parts that
are real today (steps 9, 12, 13 below). The rest is a manual checklist until a real vLLM
container exists to switch (`docs/operations/host-setup-beast.md`,
`docs/operations/inference-runtime.md`).

| Step | Action | Automated by `model.sh`? |
| --- | --- | --- |
| 1 | Select candidate | No - a human decision, see `inference/configs/README.md` |
| 2 | Compatibility preflight (section 22.2) | No - manual, per candidate |
| 3 | Memory feasibility estimate | No - `MUST BE BENCHMARKED ON PRODUCTION HARDWARE` |
| 4 | Download into `LARA_MODEL_DIR` | No |
| 5 | Write the config file | No - `inference/configs/<name>.yaml` |
| 6 | Announce and drain | **No - only meaningful for a container recreate; a registry-only switch (today's Ollama path) has nothing to drain** |
| 7 | Recreate `lara-inference` | **No - no vLLM container exists yet** |
| 8 | Runtime health check | No, same reason |
| 9 | Generation smoke test | **Yes** - `inference/scripts/smoke.sh` |
| 10 | Tool-call smoke test | Partial - `smoke.sh` reports tool-call support as info, not pass/fail |
| 11 | Benchmark | No - `docs/benchmarks/` |
| 12 | Update the registry | **Yes** - `POST`/`PATCH /admin/models` |
| 13 | Resume admission | **Yes** - a registry-only switch never paused admission |
| 14 | Record downtime | No - manual, write it here |

## Today's usage (dev, Ollama backend)

```bash
export LARA_ADMIN_KEY=lara_...
export LARA_BACKEND_URL=http://localhost:11434
scripts/model.sh <alias> ollama-dev <model_ref> <context_limit> --default "$LARA_ADMIN_KEY"
```

Verified 2026-08-12: ran against `campus-coder` -> `ollama-dev` -> `llama3:8b-instruct-q4_K_M`,
smoke test passed, registry updated, default flag set. Full command output recorded in
`docs/architecture/modes.md`.

## Once vLLM exists (production)

Steps 6-8 become real: `docker compose stop lara-inference` (after confirming no `RUNNING`
jobs via `GET /admin/jobs?status=RUNNING`, or waiting up to `LARA_DRAIN_TIMEOUT_S`), swap
`LARA_ACTIVE_MODEL_CONFIG`, `docker compose up -d lara-inference`, wait for its healthcheck,
then run `scripts/model.sh` as above with `LARA_BACKEND_URL` pointed at
`lara-inference:8000` from inside the Docker network (or a temporary loopback bind removed
immediately after). On any failure at steps 7-9, restore the previous
`LARA_ACTIVE_MODEL_CONFIG` and re-verify before investigating - this rollback is not yet
scripted and should be before this runbook is considered complete for production use.

## Downtime log

| Date | From | To | Downtime | Notes |
| --- | --- | --- | --- | --- |
| 2026-08-12 | (none) | campus-coder / ollama-dev / llama3:8b-instruct-q4_K_M | 0s (registry-only, no container recreate) | Initial dev registration via `model.sh` |
