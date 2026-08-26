"""Idempotent seed: roles, backend rows, initial model registry row (blueprint section 21.9).

Run inside the gateway container (needs app.db on the path):
    python -m database.seed.seed

Never inserts a fixed owner API key - the owner's first key is minted separately by
scripts/bootstrap-owner.sh / database.seed.bootstrap_owner, out of band, because admin
endpoints require an admin key that does not exist yet (blueprint section 21.9 point 4).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InferenceBackend, ModelRegistry, Role
from app.db.session import SessionLocal

# Seed roles: descending default priority weights. Names and weights are seed data, never
# constants in application code (blueprint section 21.3 / PRD 9.4).
ROLES = [
    {"name": "owner", "priority": 1000, "is_admin": True, "description": "Workstation owner"},
    {"name": "admin", "priority": 500, "is_admin": True, "description": "Administrator"},
    {"name": "developer", "priority": 100, "is_admin": False, "description": "Developer"},
    {"name": "researcher", "priority": 100, "is_admin": False, "description": "Researcher"},
    {"name": "member", "priority": 10, "is_admin": False, "description": "Campus member"},
]

BACKENDS = [
    {
        "name": "ollama-dev",
        "runtime": "ollama",
        "base_url": "http://host.docker.internal:11434",
        "enabled": True,
    },
    {
        "name": "vllm-prod",
        "runtime": "vllm",
        "base_url": "http://lara-inference:8000",
        # Disabled: not yet real. See docs/operations/inference-runtime.md.
        "enabled": False,
    },
]


async def seed_roles(db: AsyncSession) -> None:
    for row in ROLES:
        existing = (await db.execute(select(Role).where(Role.name == row["name"]))).scalar_one_or_none()
        if existing is None:
            db.add(Role(**row))
        else:
            existing.priority = row["priority"]
            existing.is_admin = row["is_admin"]
            existing.description = row["description"]
    await db.flush()


async def seed_backends(db: AsyncSession) -> dict[str, InferenceBackend]:
    result: dict[str, InferenceBackend] = {}
    for row in BACKENDS:
        existing = (
            await db.execute(select(InferenceBackend).where(InferenceBackend.name == row["name"]))
        ).scalar_one_or_none()
        if existing is None:
            existing = InferenceBackend(**row)
            db.add(existing)
            await db.flush()
        else:
            existing.runtime = row["runtime"]
            existing.base_url = row["base_url"]
            existing.enabled = row["enabled"]
        result[row["name"]] = existing
    return result


async def seed_models(db: AsyncSession, backends: dict[str, InferenceBackend]) -> None:
    ollama_dev = backends["ollama-dev"]
    existing = (await db.execute(select(ModelRegistry).where(ModelRegistry.alias == "campus-coder"))).scalar_one_or_none()
    if existing is None:
        db.add(
            ModelRegistry(
                alias="campus-coder",
                backend_id=ollama_dev.id,
                model_ref="llama3:8b-instruct-q4_K_M",
                quantization="q4_K_M",
                # PROVISIONAL, not empirically verified at long context on this backend.
                # Ollama's default num_ctx is 2048 unless a request overrides it; the
                # model architecture's own default is 8192. See inference/configs/ollama-dev.yaml.
                context_limit=4096,
                max_output_default=1024,
                config_file="inference/configs/ollama-dev.yaml",
                enabled=True,
                is_default=True,
                notes="Seeded from the discovered dev backend. context_limit is provisional, not benchmarked.",
            )
        )
    else:
        # Repair drift from test/dev model-registry exercises without overriding an
        # operator-selected default model. Model replacement remains an admin operation.
        existing.backend_id = ollama_dev.id
        existing.model_ref = "llama3:8b-instruct-q4_K_M"
        existing.quantization = "q4_K_M"
        existing.context_limit = 4096
        existing.max_output_default = 1024
        existing.config_file = "inference/configs/ollama-dev.yaml"
        existing.enabled = True

        default_exists = (
            await db.execute(select(ModelRegistry).where(ModelRegistry.is_default.is_(True)))
        ).scalar_one_or_none()
        if default_exists is None:
            existing.is_default = True
    await db.flush()


async def main() -> None:
    async with SessionLocal() as db:
        await seed_roles(db)
        backends = await seed_backends(db)
        await seed_models(db, backends)
        await db.commit()
    print("Seed complete: roles, backends, initial model registry row.")


if __name__ == "__main__":
    asyncio.run(main())
