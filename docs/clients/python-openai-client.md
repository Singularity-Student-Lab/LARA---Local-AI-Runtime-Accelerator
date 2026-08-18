# Client Setup — Python `openai` SDK

Both the dev backend (Ollama) and the future gateway speak the OpenAI-compatible dialect, so
the standard `openai` Python package works against either by changing `base_url`.

```python
from openai import OpenAI

# Direct against the dev backend (no auth):
client = OpenAI(base_url="http://localhost:11434/v1", api_key="not-needed")

# Through the LARA gateway (once Phase D lands):
# client = OpenAI(base_url="https://<gateway-host>/v1", api_key="lara_<key_id>.<secret>")

resp = client.chat.completions.create(
    model="llama3:8b-instruct-q4_K_M",  # or the LARA alias, e.g. "campus-coder", through the gateway
    messages=[{"role": "user", "content": "Say OK and nothing else."}],
    stream=False,
)
print(resp.choices[0].message.content)

stream = client.chat.completions.create(
    model="llama3:8b-instruct-q4_K_M",
    messages=[{"role": "user", "content": "Count 1 to 5"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
```

Verified 2026-08-12 against the dev backend directly: non-streaming and streaming both work.
Tool calling was tested and is **not supported by the currently installed model**
(`llama3:8b-instruct-q4_K_M` — see `docs/operations/dev-backend.md`), so a tool-calling agent
test (Cline, Roo Code, Continue, Aider, OpenHands) is deferred until either a tool-call-capable
model is pulled on this machine or the production vLLM backend is available. This is recorded
as an open item, not silently skipped — see `docs/operations/exit-gates.md`.
