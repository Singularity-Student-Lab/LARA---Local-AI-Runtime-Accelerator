# Development Backend — Ollama, Discovered Facts

**Status: verified 2026-08-12, on this dev machine only.** Every value below was discovered by
running the command shown, never assumed (blueprint section 2.4). Re-run `ollama list` before
trusting this file if the dev machine's installed model has changed since this date.

## Discovery commands and raw output

```text
$ ollama --version
ollama version is 0.16.3

$ ollama list
NAME                         ID              SIZE      MODIFIED
llama3:8b-instruct-q4_K_M    9b8f3f3385bf    4.9 GB    5 months ago

$ curl http://localhost:11434/v1/models
{"object":"list","data":[{"id":"llama3:8b-instruct-q4_K_M","object":"model","created":1771767485,"owned_by":"library"}]}
```

## Endpoint support matrix (verified against `inference/scripts/smoke.sh`)

| Endpoint | Support | Evidence |
| --- | --- | --- |
| `GET /v1/models` | Yes | Returns the model id above |
| `POST /v1/chat/completions`, non-streaming | Yes | Returns `usage` with real token counts |
| `POST /v1/chat/completions`, `stream=true` | Yes | SSE `data: {...}` chunks, terminated by `data: [DONE]` |
| `POST /v1/responses` | **Yes** | Full Responses-API-shaped JSON (`object":"response"`, `output[].content[].type":"output_text"`, `usage.input_tokens`/`output_tokens`). This is a real, verified fact — Ollama 0.16.3 implements it, contrary to any assumption of vLLM-only support. |
| Tool / function calling | **No, for this model** | `POST /v1/chat/completions` with a `tools` array returns `{"error":{"message":"registry.ollama.ai/library/llama3:8b-instruct-q4_K_M does not support tools", "type":"api_error"}}`. This is a model limitation, not an Ollama runtime limitation — other Ollama-served models may differ. Recorded per blueprint section 22.2: "tool calling and the chat template are the two dimensions most often skipped and most often fatal." |

**Consequence for the gateway (Phase D):** the `/v1/responses` route must not hard-code
"unsupported on Ollama" — it works here. The `501`-style unsupported response the blueprint
describes is reserved for backends/models that genuinely lack it, determined per-backend from
this table, not assumed from the runtime name.

**Consequence for agentic workloads:** `llama3:8b-instruct-q4_K_M` cannot drive tool-calling
coding agents (Cline, Roo, Continue, Aider in tool-call mode) on this backend today. This is a
real finding for `docs/clients/`, not a gateway defect. A tool-call-capable model (e.g. one
whose Ollama template declares tool support) would need to be pulled to unblock that class of
client testing on this machine.

## Container-to-host reachability (blueprint open unknown U-08, resolved for this machine)

Initial state (and current state as of this writing): Ollama is bound to `127.0.0.1:11434`
only (`ss -tlnp` shows `LISTEN 127.0.0.1:11434`), so a container on Docker's bridge network
reaching `host.docker.internal:host-gateway` gets `Could not connect to server` — bridge
traffic does not arrive as `127.0.0.1` from the host's point of view.

**Status: fix approved by the user, not yet applied.** This session's sandbox has no
passwordless `sudo`, so the systemd override below must be applied by the user directly. Once
applied, re-run the verification command in this section and update this status line.

Approved fix — a systemd override setting `OLLAMA_HOST=0.0.0.0:11434`, then
`systemctl daemon-reload` + `systemctl restart ollama`:

```text
/etc/systemd/system/ollama.service.d/override.conf:
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

**Security note, recorded honestly:** this makes Ollama reachable from any device on the same
LAN that can route to this host on port 11434, not just from Docker containers on this machine.
That is an acceptable tradeoff for a personal dev box building LARA, but it is not the posture
`lara-inference` will have in production — production vLLM never publishes a port at all
(blueprint section 3.3); the gateway reaches it over the internal-only `lara_core` Docker
network. This dev-only exposure should be narrowed (e.g. firewall Ollama's port to
`172.16.0.0/12`/Docker's bridge subnets only) or reverted when not actively developing LARA.

Verification command to re-run once the override is applied (this is the exact command that
currently fails with connection-refused, confirming the diagnosis above):

```text
$ docker run --rm --add-host=host.docker.internal:host-gateway curlimages/curl:8.11.1 \
    -fsS --max-time 5 http://host.docker.internal:11434/v1/models
# before the fix: curl: (7) Failed to connect to host.docker.internal port 11434
# after the fix, expected: 200 response with the model listed
```

`compose.yaml`'s `lara-gateway` service therefore carries:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

and `LARA_OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env.example`.

**This answer is specific to this machine (native Linux Docker).** On the production beast
(Windows 11 + WSL2 + Docker Desktop), `host.docker.internal` typically resolves automatically
without any host-side rebind — but that must be independently re-verified there, not assumed
from this record (blueprint open unknown U-08 remains open for the beast until then).
