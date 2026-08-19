"""Streaming and non-streaming proxy to a resolved backend (blueprint section 3, Session 3
point 7). The gateway never rewrites token content - it relays bytes unchanged and only adds
LARA metadata as headers (blueprint section 5.1 rule 3).

Status-code mapping follows blueprint section 5.2.2 / 20.4:
  backend unreachable / connect failure -> 502
  no response within the TTFT timeout   -> 504
  backend 5xx                            -> 502 (LARA-wrapped, not the raw backend 5xx)
  backend 4xx                            -> passed through as-is, with LARA request id added
  backend 2xx                            -> passed through unmodified

Job-lifecycle recording (Session 4) happens via the optional `recorder` (a JobRecorder), never
by reusing the request-scoped DB session inside the streaming generator - see
app/scheduler/recorder.py for why.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator

import httpx
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.api.errors import lara_error
from app.config import Settings
from app.scheduler.recorder import JobRecorder

logger = logging.getLogger("lara.gateway.proxy")


def _lara_headers(request_id: str | None, alias: str, mode: str, max_tokens_applied: bool) -> dict:
    headers = {
        "X-LARA-Mode": mode,
        "X-LARA-Model": alias,
    }
    if request_id:
        headers["X-LARA-Request-Id"] = request_id
    if max_tokens_applied:
        headers["X-LARA-Max-Tokens-Applied"] = "true"
    return headers


def _extract_usage(body: bytes) -> tuple[int | None, int | None]:
    try:
        data = json.loads(body)
        usage = data.get("usage", {})
        return usage.get("prompt_tokens") or usage.get("input_tokens"), usage.get("completion_tokens") or usage.get(
            "output_tokens"
        )
    except (json.JSONDecodeError, AttributeError):
        return None, None


async def proxy_non_streaming(
    *,
    client: httpx.AsyncClient,
    backend_url: str,
    payload: dict,
    request: Request,
    settings: Settings,
    alias: str,
    mode: str,
    max_tokens_applied: bool,
    recorder: JobRecorder | None = None,
) -> Response:
    request_id = getattr(request.state, "request_id", None)
    start = time.monotonic()
    try:
        resp = await client.post(
            backend_url,
            json=payload,
            timeout=httpx.Timeout(
                connect=settings.lara_connect_timeout_s,
                read=settings.lara_request_timeout_s,
                write=settings.lara_connect_timeout_s,
                pool=settings.lara_connect_timeout_s,
            ),
        )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        if recorder:
            await recorder.mark_failed("backend_unreachable")
        raise lara_error(502, "backend_unreachable", "The inference backend could not be reached.", request)
    except httpx.TimeoutException:
        if recorder:
            await recorder.mark_failed("ttft_timeout")
        raise lara_error(504, "ttft_timeout", "The backend did not respond in time.", request)

    ttft_ms = round((time.monotonic() - start) * 1000)
    headers = _lara_headers(request_id, alias, mode, max_tokens_applied)

    if resp.status_code >= 500:
        logger.warning("backend 5xx", extra={"status_code": resp.status_code, "request_id": request_id})
        if recorder:
            await recorder.mark_failed("upstream_5xx")
        raise lara_error(502, "upstream_5xx", f"Backend returned {resp.status_code}.", request)

    if resp.status_code >= 400:
        if recorder:
            await recorder.mark_failed("upstream_4xx")
    elif recorder:
        input_tokens, output_tokens = _extract_usage(resp.content)
        await recorder.mark_completed(ttft_ms=ttft_ms, input_tokens=input_tokens, output_tokens=output_tokens)

    return Response(content=resp.content, status_code=resp.status_code, media_type="application/json", headers=headers)


async def proxy_streaming(
    *,
    client: httpx.AsyncClient,
    backend_url: str,
    payload: dict,
    request: Request,
    settings: Settings,
    alias: str,
    mode: str,
    max_tokens_applied: bool,
    recorder: JobRecorder | None = None,
) -> Response:
    request_id = getattr(request.state, "request_id", None)
    httpx_request = client.build_request(
        "POST",
        backend_url,
        json=payload,
        timeout=httpx.Timeout(
            connect=settings.lara_connect_timeout_s,
            read=settings.lara_ttft_timeout_s,
            write=settings.lara_connect_timeout_s,
            pool=settings.lara_connect_timeout_s,
        ),
    )

    try:
        resp = await client.send(httpx_request, stream=True)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        if recorder:
            await recorder.mark_failed("backend_unreachable")
        raise lara_error(502, "backend_unreachable", "The inference backend could not be reached.", request)
    except httpx.TimeoutException:
        if recorder:
            await recorder.mark_failed("ttft_timeout")
        raise lara_error(504, "ttft_timeout", "The backend did not respond in time.", request)

    headers = _lara_headers(request_id, alias, mode, max_tokens_applied)

    if resp.status_code >= 400:
        # Real backends (verified against Ollama) return a small JSON error body immediately,
        # before any generation starts, when a streaming request is rejected outright - so
        # it is safe to buffer and pass it through rather than mid-stream.
        body = await resp.aread()
        await resp.aclose()
        if recorder:
            await recorder.mark_failed("upstream_5xx" if resp.status_code >= 500 else "upstream_4xx")
        if resp.status_code >= 500:
            raise lara_error(502, "upstream_5xx", f"Backend returned {resp.status_code}.", request)
        return Response(content=body, status_code=resp.status_code, media_type="application/json", headers=headers)

    async def relay() -> AsyncGenerator[bytes, None]:
        start = time.monotonic()
        first_chunk_at: float | None = None
        cancelled = False
        try:
            async for chunk in resp.aiter_raw():
                if await request.is_disconnected():
                    cancelled = True
                    logger.info("client disconnected mid-stream", extra={"request_id": request_id})
                    break
                if first_chunk_at is None:
                    first_chunk_at = time.monotonic()
                if time.monotonic() - start > settings.lara_request_timeout_s:
                    logger.warning("generation timeout, aborting stream", extra={"request_id": request_id})
                    if recorder:
                        await recorder.mark_failed("generation_timeout")
                    return
                yield chunk
            else:
                if recorder:
                    ttft_ms = round((first_chunk_at - start) * 1000) if first_chunk_at else None
                    await recorder.mark_completed(ttft_ms=ttft_ms, input_tokens=None, output_tokens=None)
            if cancelled and recorder:
                await recorder.mark_cancelled("client_disconnect")
        finally:
            await resp.aclose()

    return StreamingResponse(relay(), status_code=resp.status_code, media_type="text/event-stream", headers=headers)
