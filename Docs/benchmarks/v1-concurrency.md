# V1 Concurrency Benchmarks

**Status: PENDING — MUST BE BENCHMARKED ON PRODUCTION HARDWARE.** Nothing in this file may be
filled in from anything measured on this development machine (blueprint section 24.1). The
dev GPU is an RTX 3050 6GB laptop card; the production target is an RTX 5060 Ti 16GB - not
comparable, not even directionally.

The harness itself (`inference/scripts/smoke.sh`'s methodology, extended per blueprint Session
2 section 7) is ready to run unmodified once `docs/operations/host-setup-beast.md` closes and
a production vLLM backend exists. What's proven on this dev machine instead: the *scheduler's*
concurrency correctness (exactly 3 running under load) - see `docs/architecture/scheduler.md`
and `tests/load/test_concurrency.py` - which is a real, verified result, just not a performance
one.

## Required measurements (blueprint Session 7 point 6)

| Scenario | TTFT | Tokens/s | Wall-clock | VRAM | GPU util | CPU | RAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 concurrent job | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| 2 concurrent jobs | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| 3 concurrent jobs | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| 3 concurrent, long context | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| Sustained load (stability) | PENDING | n/a | PENDING | PENDING | PENDING | PENDING | PENDING |
| Game Dev Mode + real Unity/Unreal workload | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |

Every row, when filled in, must record: model config file used, quantization, context
settings, mode, host state (what else was running), vLLM image tag, and date - a result
without its configuration is not a result (blueprint Session 2 section 7 rule).

## What this unblocks

- `LARA_TTFT_TIMEOUT_S`, `LARA_REQUEST_TIMEOUT_S`, `LARA_QUEUE_TIMEOUT_S` real values (currently
  provisional defaults in `.env.example`, sized for dev-GPU generation speed, not production).
- Whether the 3-job global ceiling (`LARA_MAX_ACTIVE_JOBS`) is actually safe at the working
  context length on the production card - if not, that's a finding to escalate as a PRD
  revision, not silently change (blueprint Session 7 point 6).
- `LARA_PRESSURE_*` thresholds for Game Dev Mode (currently dev-GPU-sized provisional values).
