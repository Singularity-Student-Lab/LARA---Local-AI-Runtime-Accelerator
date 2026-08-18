# Client Setup — curl

Verified against the dev backend directly (`http://localhost:11434`) on 2026-08-12. Once the
gateway exists (Phase C onward), replace the base URL with the gateway's and add the
`Authorization: Bearer lara_<key_id>.<secret>` header — see `docs/security/auth.md`.

## Non-streaming

```bash
curl -s http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3:8b-instruct-q4_K_M",
    "messages": [{"role": "user", "content": "Say OK and nothing else."}],
    "stream": false,
    "max_tokens": 10
  }'
```

Verified response shape includes `usage.prompt_tokens` / `usage.completion_tokens`.

## Streaming

```bash
curl -s --no-buffer http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3:8b-instruct-q4_K_M",
    "messages": [{"role": "user", "content": "Count 1 to 5"}],
    "stream": true,
    "max_tokens": 30
  }'
```

Verified: SSE `data: {...}` chunks arrive incrementally, terminated by a final `data: [DONE]`
line (`--no-buffer` is required or curl will hold output until the stream closes).

## Through the LARA gateway (once Phase D lands)

```bash
curl -s https://<gateway-host>/v1/chat/completions \
  -H "Authorization: Bearer lara_<key_id>.<secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "campus-coder",
    "messages": [{"role": "user", "content": "Say OK and nothing else."}],
    "stream": false
  }'
```

Note `model` becomes the LARA alias (`campus-coder`), not the raw backend model id — the
gateway resolves it (blueprint section 20.3).
