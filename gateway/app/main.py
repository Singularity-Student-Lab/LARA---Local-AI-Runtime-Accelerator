from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import DBAPIError
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.admin.analytics import router as admin_analytics_router
from app.api.admin.jobs import router as admin_jobs_router
from app.api.admin.mode import router as admin_mode_router
from app.api.admin.models import router as admin_models_router
from app.api.admin.users import router as admin_users_router
from app.api.lara.analytics import router as lara_analytics_router
from app.api.lara.jobs import router as lara_jobs_router
from app.api.security import AuthFailThrottle, RateLimiter
from app.api.v1.chat import router as v1_chat_router
from app.api.v1.models import router as v1_models_router
from app.config import get_settings
from app.db.session import SessionLocal
from app.logging_config import configure_logging
from app.middleware import AuthFailThrottleMiddleware, RequestContextMiddleware, RequestSizeLimitMiddleware
from app.models.backend_client import build_backend_client
from app.modes.policy import build_mode_policies
from app.modes.pressure import PressureEvaluator, PressureThresholds, sample_gpu
from app.monitoring.health import router as health_router
from app.monitoring.status import router as status_router
from app.scheduler.queue import Scheduler
from app.scheduler.reconcile import reconcile_orphaned_jobs
from app.scheduler.registry import JobTaskRegistry

configure_logging()
logger = logging.getLogger("lara.gateway")

settings = get_settings()


async def _pressure_sampling_loop(app: FastAPI) -> None:
    evaluator: PressureEvaluator = app.state.pressure_evaluator
    while True:
        try:
            sample = await sample_gpu()
            evaluator.ingest(sample)
        except Exception:
            logger.exception("pressure sampling loop error")
        await asyncio.sleep(settings.lara_gpu_sample_interval_s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.backend_client = build_backend_client(settings)
    app.state.scheduler = Scheduler(
        max_active_jobs=settings.lara_max_active_jobs,
        per_user_max_active=settings.lara_per_user_max_active,
        queue_max_depth=settings.lara_queue_max_depth,
    )
    app.state.job_tasks = JobTaskRegistry()
    app.state.rate_limiter = RateLimiter(
        max_requests=settings.lara_rate_limit_requests, window_s=settings.lara_rate_limit_window_s
    )
    app.state.auth_fail_throttle = AuthFailThrottle(
        threshold=settings.lara_auth_fail_threshold,
        window_s=settings.lara_auth_fail_window_s,
        block_s=settings.lara_auth_fail_block_s,
    )
    app.state.mode_policies = build_mode_policies(settings)
    app.state.pressure_evaluator = PressureEvaluator(
        window_samples=settings.lara_pressure_window_samples,
        hysteresis_samples=settings.lara_pressure_hysteresis_samples,
        thresholds=PressureThresholds(
            vram_moderate=settings.lara_pressure_vram_moderate,
            vram_high=settings.lara_pressure_vram_high,
            vram_critical=settings.lara_pressure_vram_critical,
            util_moderate=settings.lara_pressure_util_moderate,
            util_high=settings.lara_pressure_util_high,
            util_critical=settings.lara_pressure_util_critical,
            temp_critical=settings.lara_pressure_temp_critical,
        ),
    )
    pressure_task = asyncio.create_task(_pressure_sampling_loop(app))

    # Reconciliation must run before the gateway accepts traffic, so active/queue counts
    # start from truth (blueprint section 5.2.4).
    async with SessionLocal() as db:
        await reconcile_orphaned_jobs(db)

    logger.info(
        "gateway starting",
        extra={
            "lara_env": settings.lara_env,
            "max_active_jobs": settings.lara_max_active_jobs,
            "worker_note": "single worker process is a correctness requirement, not a default",
        },
    )
    try:
        yield
    finally:
        pressure_task.cancel()
        await app.state.backend_client.aclose()


app = FastAPI(title="LARA Gateway", docs_url=None, redoc_url=None, lifespan=lifespan)

# Starlette wraps middleware so the LAST one added() is OUTERMOST - i.e. runs first on the
# way in. Added in reverse of desired execution order: RequestContextMiddleware first (so
# every later rejection, including a throttled or oversized request, still gets a request id
# and a log line), then AuthFailThrottleMiddleware, then RequestSizeLimitMiddleware innermost,
# closest to the route handler.
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(AuthFailThrottleMiddleware)
app.add_middleware(RequestContextMiddleware)

async def database_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """A real gap found by testing, not by inspection: killing lara-database and hitting any
    authenticated endpoint surfaced a raw 500 with a full traceback, not the blueprint's
    intended failure mode - "Database unreachable ... Requests that need identity fail closed
    ... 503" (blueprint section 3, Session 3 Failure Modes table).

    Registered for TWO exception types, not one, because testing this for real surfaced a
    second gap: a DNS-resolution failure (Docker cannot resolve "lara-database" while that
    container is stopped) raises a bare `socket.gaierror` (an OSError) that never gets wrapped
    in SQLAlchemy's own `DBAPIError` at all - it happens at connection-establishment, before
    SQLAlchemy's dbapi-exception-translation layer sees it. A handler registered only for
    DBAPIError silently missed this case in testing. OSError is broad, but scoped correctly
    here: this handler is only reachable from a route that touches the DB via a dependency,
    so an OSError arriving at this handler in practice means the database connection failed,
    not an unrelated filesystem/network error elsewhere in the request path."""
    logger.error(
        "database error", extra={"request_id": getattr(request.state, "request_id", None), "exc_type": type(exc).__name__}
    )
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "type": "database_unavailable",
                "message": "The service is temporarily unavailable. Try again shortly.",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


app.add_exception_handler(DBAPIError, database_unavailable_handler)
app.add_exception_handler(OSError, database_unavailable_handler)


app.include_router(health_router)
app.include_router(status_router)
app.include_router(v1_models_router)
app.include_router(v1_chat_router)
app.include_router(admin_users_router)
app.include_router(lara_jobs_router)
app.include_router(admin_jobs_router)
app.include_router(admin_mode_router)
app.include_router(admin_models_router)
app.include_router(admin_analytics_router)
app.include_router(lara_analytics_router)
