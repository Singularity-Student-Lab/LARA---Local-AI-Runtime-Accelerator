"""Alias resolution: clients only ever see LARA aliases, never a backend model id, filesystem
path, or repository id (blueprint section 22.1 / PRD 7.3)."""

from __future__ import annotations

import dataclasses

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InferenceBackend, ModelRegistry


@dataclasses.dataclass
class ResolvedModel:
    registry_row: ModelRegistry
    backend: InferenceBackend


async def list_enabled_aliases(db: AsyncSession) -> list[ModelRegistry]:
    result = await db.execute(select(ModelRegistry).where(ModelRegistry.enabled.is_(True)))
    return list(result.scalars().all())


async def resolve_alias(db: AsyncSession, alias: str) -> ResolvedModel | None:
    row = (await db.execute(select(ModelRegistry).where(ModelRegistry.alias == alias))).scalar_one_or_none()
    if row is None or not row.enabled:
        return None
    backend = (
        await db.execute(select(InferenceBackend).where(InferenceBackend.id == row.backend_id))
    ).scalar_one_or_none()
    if backend is None or not backend.enabled:
        return None
    return ResolvedModel(registry_row=row, backend=backend)


async def get_default_alias(db: AsyncSession) -> ModelRegistry | None:
    return (
        await db.execute(select(ModelRegistry).where(ModelRegistry.is_default.is_(True)))
    ).scalar_one_or_none()
