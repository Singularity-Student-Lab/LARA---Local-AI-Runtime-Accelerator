# Inference Runtime Status

## Production (vLLM on the beast) — formally blocked

**Status: blocked, documented bypass in effect** (blueprint section 4.3 rule 4).

The production vLLM path cannot be attempted in this development context: there is no
Windows 11 + WSL2 + RTX 5060 Ti 16GB host available. Attempting it would mean guessing the
pinned image tag, the GPU-generation kernel compatibility, and the memory/context arguments —
exactly the fabrication the blueprint's anti-hallucination rules forbid (section 0.3).

Blocker: no production hardware available in this development context.

Bypass in effect: Sessions 3–5 (gateway, auth, database, scheduler, modes, model registry)
proceed against the Ollama development backend (`inference/configs/ollama-dev.yaml`,
`docs/operations/dev-backend.md`), per the blueprint's own documented exception. This bypass
does not close the Session 2 production exit gate — see `docs/operations/exit-gates.md` — and
no performance claim is made anywhere in this repository until it does.

To close this blocker: execute `docs/operations/host-setup-beast.md` in full, then return to
blueprint Session 2 section "1. Pin the vLLM image" through "7. Benchmark methodology" and fill
in `inference/configs/vllm-prod.yaml` from real, measured values only.

## Development (Ollama) — open, working

See `docs/operations/dev-backend.md` for the full endpoint-support matrix, and
`inference/configs/ollama-dev.yaml` for the active profile. Summary: `/v1/models`,
`/v1/chat/completions` (streaming and non-streaming), and `/v1/responses` all work.
Tool/function calling does not work with the currently installed model.

`inference/scripts/smoke.sh <base_url> <model_id>` is the one-command verification for either
backend; it was run and passed against the dev backend on 2026-08-12.
