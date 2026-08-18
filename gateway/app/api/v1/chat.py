from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.api.errors import estimate_tokens, lara_error
from app.auth.dependencies import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.proxy import proxy_non_streaming, proxy_streaming
from app.models.registry import get_default_alias, list_enabled_aliases, resolve_alias
from app.modes.effective import apply_to_scheduler, compute_effective_policy
from app.scheduler import lifecycle
from app.scheduler.errors import QueueFullError, QueueTimeoutError
from app.scheduler.recorder import JobRecorder

router = APIRouter()

_DISCONNECT_POLL_INTERVAL_S = 1.0


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _handle_completion(request, db, ctx, settings, path="/v1/chat/completions")


# Verified against the current dev backend (docs/operations/dev-backend.md): Ollama 0.16.3
# genuinely implements /v1/responses, so it is proxied like chat/completions rather than
# hard-coded as unsupported. A backend that lacks it (to be verified for vLLM once the beast
# exists) will return its own 404/501, which passes through as-is below - a real backend
# answer, not a fabricated one.
@router.post("/v1/responses")
async def responses_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
) -> Response:
    return await _handle_completion(request, db, ctx, settings, path="/v1/responses")


async def _watch_disconnect(request: Request, target_task: asyncio.Task) -> None:
    """Cancels target_task as soon as the client disconnects, whether it is still queued or
    already running (blueprint Testing T-S4-09, T-S4-10)."""
    try:
        while not target_task.done():
            if await request.is_disconnected():
                target_task.cancel()
                return
            await asyncio.sleep(_DISCONNECT_POLL_INTERVAL_S)
    except asyncio.CancelledError:
        pass


async def _handle_completion(
    request: Request, db: AsyncSession, ctx: AuthContext, settings: Settings, *, path: str
) -> Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise lara_error(400, "malformed_request", "Request body is not valid JSON.", request)
    if not isinstance(body, dict):
        raise lara_error(400, "malformed_request", "Request body must be a JSON object.", request)

    alias = body.get("model")
    if alias is None:
        default_row = await get_default_alias(db)
        if default_row is None:
            raise lara_error(503, "no_default_model", "No default model is configured.", request)
        alias = default_row.alias
    elif not isinstance(alias, str):
        raise lara_error(400, "malformed_request", "'model' must be a string.", request)

    resolved = await resolve_alias(db, alias)
    if resolved is None:
        valid = [row.alias for row in await list_enabled_aliases(db)]
        raise lara_error(404, "unknown_model", f"Unknown or disabled model alias '{alias}'. Valid: {valid}", request)

    # Coarse pre-flight context check (blueprint section 20.3 rule 2). estimate_tokens() is a
    # documented approximation, not real tokenization - see app/api/errors.py.
    if path == "/v1/chat/completions":
        messages = body.get("messages")
        if not isinstance(messages, list):
            raise lara_error(400, "malformed_request", "'messages' must be a list.", request)
        text = "".join(m.get("content", "") for m in messages if isinstance(m, dict) and isinstance(m.get("content"), str))
    else:
        text = body.get("input", "") if isinstance(body.get("input"), str) else ""

    if estimate_tokens(text) > resolved.registry_row.context_limit:
        raise lara_error(
            400,
            "context_too_large",
            f"Estimated request size exceeds this model's context limit ({resolved.registry_row.context_limit} tokens).",
            request,
        )

    # Output-token clamp. Real mode-aware caps land in Phase F; for now the only ceiling is
    # the registry row's max_output_default, per blueprint section 20.3 rule 1.
    max_tokens_applied = False
    ceiling = resolved.registry_row.max_output_default
    if ceiling is not None:
        requested = body.get("max_tokens")
        if isinstance(requested, int) and requested > ceiling:
            body["max_tokens"] = ceiling
            max_tokens_applied = True

    payload = dict(body)
    payload["model"] = resolved.registry_row.model_ref

    backend_url = f"{resolved.backend.base_url.rstrip('/')}{path}"
    client = request.app.state.backend_client
    scheduler = request.app.state.scheduler
    task_registry = request.app.state.job_tasks
    stream = bool(body.get("stream", False))

    # Mode + GPU-pressure policy (blueprint section 5.3.1 point 3): resolved fresh per
    # request since mode/pressure are process-global and can change between requests.
    effective = await compute_effective_policy(request, db, is_owner=(ctx.role.name == "owner"))
    apply_to_scheduler(request, effective)
    effective_priority = ctx.role.priority + effective.priority_bonus

    # Job row created at RECEIVED before admission, so rejections are countable
    # (blueprint section 5.2.1 / 21.6). request_id reuses request.state.request_id (assigned
    # by RequestContextMiddleware) rather than generating a second, different id - see the
    # docstring on lifecycle.create_received for why that split caused a real bug.
    job = await lifecycle.create_received(
        db,
        request_id=uuid.UUID(request.state.request_id),
        user_id=ctx.user.id,
        key_id=ctx.api_key.key_id,
        model_alias=alias,
        backend_name=resolved.backend.name,
        mode=effective.mode,
        effective_priority=effective_priority,
        stream=stream,
    )
    request_id_str = str(job.request_id)

    this_task = asyncio.current_task()
    task_registry.register(request_id_str, this_task)
    watcher = asyncio.create_task(_watch_disconnect(request, this_task))

    await lifecycle.mark_queued(db, job)

    try:
        async with scheduler.admit(
            user_id=str(ctx.user.id),
            effective_priority=effective_priority,
            queue_timeout_s=settings.lara_queue_timeout_s,
        ):
            await lifecycle.mark_running(db, job)

            recorder = JobRecorder(job.request_id)
            proxy_fn = proxy_streaming if stream else proxy_non_streaming
            return await proxy_fn(
                client=client,
                backend_url=backend_url,
                payload=payload,
                request=request,
                settings=settings,
                alias=alias,
                mode=effective.mode,
                max_tokens_applied=max_tokens_applied,
                recorder=recorder,
            )
    except QueueFullError:
        await lifecycle.mark_rejected(db, job, "queue_full")
        raise lara_error(429, "queue_full", "The queue is at capacity. Try again shortly.", request)
    except QueueTimeoutError:
        await lifecycle.mark_failed(db, job, "queue_timeout")
        raise lara_error(503, "queue_timeout", "The request waited longer than the configured queue timeout.", request)
    except asyncio.CancelledError:
        # Either the explicit /cancel endpoint already wrote the terminal state (see
        # app/api/lara/jobs.py) or this is a genuine disconnect caught by the watcher above
        # before the streaming generator's own disconnect check ever ran (e.g. while still
        # queued). Recorder writes are idempotent-safe: if the row is already terminal this
        # just re-sets the same fields.
        recorder = JobRecorder(job.request_id)
        await recorder.mark_cancelled("client_disconnect")
        raise
    finally:
        task_registry.unregister(request_id_str)
        watcher.cancel()
