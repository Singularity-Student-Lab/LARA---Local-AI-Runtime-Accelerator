from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.security import client_source_hash
from app.config import get_settings

logger = logging.getLogger("lara.gateway")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, times the request, logs a single structured line per request.
    Never logs the Authorization header or request/response bodies (PRD 12.4, 16.4)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        response.headers["X-LARA-Request-Id"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects oversized bodies via Content-Length before any handler or backend call runs
    (blueprint section 3.4 point 3 / Testing T-S3-15)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                length = None
            if length is not None and length > settings.lara_max_request_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "type": "request_too_large",
                            "message": "Request body exceeds the configured size limit.",
                            "request_id": getattr(request.state, "request_id", None),
                        }
                    },
                )
        return await call_next(request)


class AuthFailThrottleMiddleware(BaseHTTPMiddleware):
    """Blocks a source (salted IP hash) after repeated authentication failures, and records
    every failure and block hit as an audit event with the source address (blueprint section
    6, "Failed-authentication throttling" / Security Considerations). Never touches routes
    that don't authenticate, and never blocks based on anything but the 401 status the auth
    dependency already produced - this middleware does not re-implement auth, only meters it.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        throttle = request.app.state.auth_fail_throttle
        source = client_source_hash(
            request, trust_proxy_headers=settings.lara_trusted_proxy_headers, pepper=settings.lara_api_key_pepper
        )

        if throttle.is_blocked(source):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "type": "auth_fail_throttled",
                        "message": "Too many authentication failures from this source. Try again later.",
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

        response = await call_next(request)
        if response.status_code == 401:
            throttle.record_failure(source)
        return response
