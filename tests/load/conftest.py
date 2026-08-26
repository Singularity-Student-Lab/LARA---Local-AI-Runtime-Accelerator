"""Load test fixtures. Prerequisites:
    docker compose up -d lara-database lara-gateway
    docker compose --profile test up -d lara-stub-backend

Registers a temporary backend+model row pointing at the deterministic stub backend
(tests/load/stub_backend/app.py) by running a small script inside the already-built
lara-gateway container (which already has SQLAlchemy/asyncpg and the app package on its
PYTHONPATH) via stdin, rather than baking test code into the production-ish gateway image.
"""

from __future__ import annotations

import subprocess
import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8080"
REPO_ROOT = __file__.rsplit("/tests/", 1)[0]

_SETUP_SCRIPT = """
import asyncio
from sqlalchemy import select
from app.db.models import InferenceBackend, ModelRegistry
from app.db.session import SessionLocal

async def main():
    async with SessionLocal() as db:
        backend = (await db.execute(select(InferenceBackend).where(InferenceBackend.name == "stub-test"))).scalar_one_or_none()
        if backend is None:
            backend = InferenceBackend(name="stub-test", runtime="ollama", base_url="http://lara-stub-backend:9000", enabled=True)
            db.add(backend)
            await db.flush()
        model = (await db.execute(select(ModelRegistry).where(ModelRegistry.alias == "stub-coder"))).scalar_one_or_none()
        if model is None:
            model = ModelRegistry(
                alias="stub-coder", backend_id=backend.id, model_ref="stub-model",
                context_limit=100000, max_output_default=1024, enabled=True, is_default=False,
                notes="tests/load fixture, deterministic stub backend",
            )
            db.add(model)
        await db.commit()

asyncio.run(main())
"""

_TEARDOWN_SCRIPT = """
import asyncio
from sqlalchemy import select
from app.db.models import ModelRegistry, InferenceBackend
from app.db.session import SessionLocal

async def main():
    async with SessionLocal() as db:
        model = (await db.execute(select(ModelRegistry).where(ModelRegistry.alias == "stub-coder"))).scalar_one_or_none()
        if model is not None:
            await db.delete(model)
        backend = (await db.execute(select(InferenceBackend).where(InferenceBackend.name == "stub-test"))).scalar_one_or_none()
        if backend is not None:
            await db.delete(backend)
        await db.commit()

asyncio.run(main())
"""


def _run_in_gateway(script: str) -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "lara-gateway", "python", "-"],
        input=script,
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )


@pytest.fixture(scope="session", autouse=True)
def stub_model_alias():
    _run_in_gateway(_SETUP_SCRIPT)
    yield "stub-coder"
    _run_in_gateway(_TEARDOWN_SCRIPT)


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def admin_key() -> str:
    username = f"pytest-load-admin-{uuid.uuid4().hex[:8]}"
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "lara-gateway", "python", "-m",
            "database.seed.bootstrap_owner", "--username", username,
            "--display-name", "Pytest Load Admin", "--label", "pytest-load",
        ],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT,
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("lara_"):
            return line
    raise RuntimeError(f"could not parse bootstrap output:\n{result.stdout}\n{result.stderr}")


def new_user_key(base_url: str, admin_key: str, *, role: str = "member") -> str:
    username = f"pytest-load-user-{uuid.uuid4().hex[:8]}"
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        user = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_key}"},
            json={"username": username, "display_name": username, "role": role},
        )
        user.raise_for_status()
        key = client.post(
            f"/admin/users/{user.json()['id']}/api-keys",
            headers={"Authorization": f"Bearer {admin_key}"},
            json={"label": "pytest-load"},
        )
        key.raise_for_status()
        return key.json()["api_key"]
