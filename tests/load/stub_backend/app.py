"""A tiny OpenAI-compatible stub backend for deterministic scheduler load tests.

Real generation duration on this dev GPU varies with load and isn't controllable, which makes
"exactly 3 running, 7 queued" hard to observe reliably. This stub sleeps a fixed, configurable
duration before responding, so concurrency tests are fast and deterministic. It never
substitutes for tests/production - see blueprint section 24.1: this stub proves the SCHEDULER
is correct, never a claim about model performance.
"""

from __future__ import annotations

import asyncio
import os
import time

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

app = FastAPI()

DELAY_S = float(os.environ.get("LARA_STUB_DELAY_S", "2.0"))
MODEL_ID = os.environ.get("LARA_STUB_MODEL_ID", "stub-model")


@app.get("/v1/models")
async def models() -> dict:
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model"}]}


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    body = await request.json()
    if body.get("stream"):
        async def gen():
            await asyncio.sleep(DELAY_S)
            yield b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":null}]}\n\n'
            yield b"data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    await asyncio.sleep(DELAY_S)
    return JSONResponse(
        {
            "id": f"stub-{time.time_ns()}",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    )
