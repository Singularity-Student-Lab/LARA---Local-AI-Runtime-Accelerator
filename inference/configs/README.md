# Model Configuration Files

One YAML file per model profile. Each file is the single source of truth for how the
corresponding inference runtime is started (blueprint section 22.3). No model-specific value
may appear in application code (PRD Appendix D rule 3 / master task 35) — the gateway only ever
reads the `models` database table (alias, backend, context limit), never these files directly;
these files are read by the runtime start procedure / `scripts/model.sh`.

| Field | Meaning |
| --- | --- |
| `alias` | The LARA-facing model name clients send as `model`. Matches a `models.alias` row. |
| `backend` | Which `inference_backends` row this profile starts (`ollama-dev`, `vllm-prod`). |
| `model_ref` | The real model id/path as that backend expects it. |
| `served_model_name` | The id the backend advertises on its own `/v1/models`. |
| `quantization`, `dtype` | Only set if the runtime accepts them as arguments. |
| `max_model_len`, `gpu_memory_utilization` | vLLM-only. Must be benchmarked, never guessed. |
| `verified_on_image` / `verified_at` / `notes` | Recorded facts, not runtime arguments. |

Current files:

- `ollama-dev.yaml` — the real, discovered dev backend (blueprint section 2.4). Usable today.
- `vllm-prod.yaml` — placeholder. Every runtime-critical field is `UNKNOWN — MUST BE VERIFIED`
  until `docs/operations/host-setup-beast.md` closes and Session 2's production exit gate is
  run for real. Do not fill these in from guesswork; a wrong `gpu_memory_utilization` or
  `max_model_len` fails loudly (OOM) or silently (truncated context), neither of which should
  be discovered on the beast for the first time in front of users.
- `<name>-gamedev.yaml` — expected once a production model is selected (Session 5): same
  weights, smaller memory fraction, shorter context, for extended game-dev sessions.
