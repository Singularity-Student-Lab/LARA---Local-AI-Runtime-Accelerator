# V1 Agentic Coding Benchmark

**Status: PENDING.** Requires a production model behind vLLM (blueprint Session 7 point 7 /
PRD 17.3). Simple chat prompts are explicitly not the primary benchmark - this is.

## Fixed elements (to define once a candidate model is selected)

| Element | Value |
| --- | --- |
| Starting repository and commit | PENDING |
| Task statement | PENDING - e.g. "implement a small REST endpoint, write tests, run them, fix failures until green" |
| Agent and agent version | PENDING - see `docs/clients/` for candidates verified against this backend |
| Client configuration | PENDING |
| Model alias and config file | PENDING |
| Mode | PENDING |
| Host state | PENDING |

## Metrics (blueprint section 24.4)

| Metric | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| Task completion (yes/no, failure point if no) | PENDING | PENDING | PENDING |
| Test pass rate at the end | PENDING | PENDING | PENDING |
| Agent turns | PENDING | PENDING | PENDING |
| Failed tool calls (count + cause) | PENDING | PENDING | PENDING |
| Total input/output tokens | PENDING | PENDING | PENDING |
| Wall-clock (including queue wait) | PENDING | PENDING | PENDING |

**Engineering Note carried from the blueprint**: failed tool calls are the metric that most
often separates a model that benchmarks well from one actually usable by a coding agent -
weight it heavily in the selection decision once real numbers exist.

## What's already known, honestly, from this dev machine

`docs/operations/dev-backend.md` recorded a real, relevant finding: the currently-installed
dev model (`llama3:8b-instruct-q4_K_M`) does **not** support tool calling on Ollama
(`"does not support tools"` returned directly by the backend). This means an agentic benchmark
cannot be run meaningfully against the current dev backend at all - not a benchmark result, but
a real constraint on which candidate models are even worth measuring here versus waiting for
the beast.
