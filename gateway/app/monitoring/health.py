"""GET /health - unauthenticated, minimal by design (blueprint section 3, Testing T-S6-01).

Reachable through the tunnel from Session 6 onward, so this must never reveal version
strings, dependency state, model names, or any internal detail (PRD 16.4)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
