"""GET/POST /admin/models, PATCH /admin/models/{alias} (blueprint section 5.3.4).

Clients only ever see aliases through /v1/models; these endpoints manage the registry rows
that alias resolution reads from (blueprint section 22.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.errors import lara_error
from app.auth.dependencies import AuthContext, require_admin
from app.db.models import AuditEvent, InferenceBackend, ModelRegistry
from app.db.session import get_db

router = APIRouter()


class CreateModelRequest(BaseModel):
    alias: str
    backend_name: str
    model_ref: str
    quantization: str | None = None
    context_limit: int
    max_output_default: int | None = None
    config_file: str | None = None
    enabled: bool = True
    is_default: bool = False
    notes: str | None = None


class PatchModelRequest(BaseModel):
    enabled: bool | None = None
    is_default: bool | None = None
    context_limit: int | None = None
    max_output_default: int | None = None
    notes: str | None = None


def _model_out(row: ModelRegistry, backend_name: str) -> dict:
    return {
        "alias": row.alias,
        "backend": backend_name,
        "model_ref": row.model_ref,
        "quantization": row.quantization,
        "context_limit": row.context_limit,
        "max_output_default": row.max_output_default,
        "config_file": row.config_file,
        "enabled": row.enabled,
        "is_default": row.is_default,
        "notes": row.notes,
    }


@router.get("/admin/models")
async def list_models(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> list[dict]:
    result = await db.execute(select(ModelRegistry, InferenceBackend).join(InferenceBackend))
    return [_model_out(m, b.name) for m, b in result.all()]


@router.post("/admin/models", status_code=201)
async def create_model(
    request: Request,
    body: CreateModelRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    backend = (
        await db.execute(select(InferenceBackend).where(InferenceBackend.name == body.backend_name))
    ).scalar_one_or_none()
    if backend is None:
        raise lara_error(400, "unknown_backend", f"Unknown backend '{body.backend_name}'.", request)

    existing = (await db.execute(select(ModelRegistry).where(ModelRegistry.alias == body.alias))).scalar_one_or_none()
    if existing is not None:
        raise lara_error(409, "duplicate_alias", f"Alias '{body.alias}' already exists.", request)

    if body.is_default:
        await db.execute(ModelRegistry.__table__.update().values(is_default=False).where(ModelRegistry.is_default.is_(True)))

    row = ModelRegistry(
        alias=body.alias,
        backend_id=backend.id,
        model_ref=body.model_ref,
        quantization=body.quantization,
        context_limit=body.context_limit,
        max_output_default=body.max_output_default,
        config_file=body.config_file,
        enabled=body.enabled,
        is_default=body.is_default,
        notes=body.notes,
    )
    db.add(row)
    db.add(AuditEvent(actor_user_id=ctx.user.id, event_type="model.create", target=body.alias, detail={}))
    await db.commit()
    return _model_out(row, backend.name)


@router.patch("/admin/models/{alias}")
async def patch_model(
    request: Request,
    alias: str,
    body: PatchModelRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> dict:
    row = (await db.execute(select(ModelRegistry).where(ModelRegistry.alias == alias))).scalar_one_or_none()
    if row is None:
        raise lara_error(404, "unknown_alias", f"Unknown alias '{alias}'.", request)

    changes: dict = {}
    if body.is_default is True:
        await db.execute(ModelRegistry.__table__.update().values(is_default=False).where(ModelRegistry.is_default.is_(True)))
        row.is_default = True
        changes["is_default"] = True
    if body.enabled is not None:
        row.enabled = body.enabled
        changes["enabled"] = body.enabled
    if body.context_limit is not None:
        row.context_limit = body.context_limit
        changes["context_limit"] = body.context_limit
    if body.max_output_default is not None:
        row.max_output_default = body.max_output_default
        changes["max_output_default"] = body.max_output_default
    if body.notes is not None:
        row.notes = body.notes

    if changes:
        event_type = "model.enable" if changes.get("enabled") else "model.update"
        db.add(AuditEvent(actor_user_id=ctx.user.id, event_type=event_type, target=alias, detail=changes))
    await db.commit()

    backend = (await db.execute(select(InferenceBackend).where(InferenceBackend.id == row.backend_id))).scalar_one()
    return _model_out(row, backend.name)
