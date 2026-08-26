# Production Model Selection

**Status: PENDING. Until this file has real numbers, LARA has no production model**
(blueprint Session 7 point 8 - this sentence is load-bearing, not decoration).

Selection order, per the blueprint: agentic task completion first
(`docs/benchmarks/v1-agentic.md`), tool-call reliability second, then tokens/second, VRAM
headroom, and behavior under 3 concurrent jobs (`docs/benchmarks/v1-concurrency.md`).

## Candidates considered

| Candidate | Architecture/format | Quantization | License | Tool-call template | Preflight result |
| --- | --- | --- | --- | --- | --- |
| `llama3:8b-instruct-q4_K_M` (dev backend, real, discovered) | Llama 3, GGUF | q4_K_M | Meta Llama 3 Community License | **No** - verified, backend rejects tool calls for this model | Ruled out for the agentic primary workload on this specific backend/model combination; still usable for non-tool-calling client testing |
| (production candidates) | PENDING | PENDING | PENDING | PENDING | PENDING - requires the beast, see `docs/operations/host-setup-beast.md` and `inference/configs/vllm-prod.yaml` |

## Decision

**Not yet made.** Record here, dated, once real evidence exists: the winner, the runner-up,
and why - per blueprint's own rule that this file is the only place a model is "selected," and
an unfilled file means no selection has happened, not an implicit default.
