from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthContext, get_auth_context
from app.db.session import get_db
from app.models.registry import list_enabled_aliases

router = APIRouter()


@router.get("/v1/models")
async def list_models(
    db: AsyncSession = Depends(get_db),
    _ctx: AuthContext = Depends(get_auth_context),
) -> dict:
    rows = await list_enabled_aliases(db)
    return {
        "object": "list",
        "data": [{"id": row.alias, "object": "model", "owned_by": "lara"} for row in rows],
    }
