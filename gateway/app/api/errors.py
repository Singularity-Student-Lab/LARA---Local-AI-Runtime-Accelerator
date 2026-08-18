"""Uniform LARA error body shape (blueprint section 20.3). Never includes internal hostnames,
container names, file paths, or stack traces."""

from __future__ import annotations

from fastapi import HTTPException
from starlette.requests import Request


def lara_error(status_code: int, error_type: str, message: str, request: Request) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "type": error_type,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token), used only for a coarse pre-flight context check.
    This is NOT real tokenization - it is deliberately conservative and documented as an
    approximation, never presented as an exact count (blueprint section 0.3: no invented
    precision)."""
    return max(1, len(text) // 4)
