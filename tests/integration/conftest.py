"""Integration test fixtures. Run against the real gateway+database compose stack on this
dev machine (blueprint section 24.1: application-layer tests run against the dev backend,
never against production hardware claims).

Prerequisite: `docker compose up -d` with a healthy lara-gateway on 127.0.0.1:8080.
"""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import uuid

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8080"


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def admin_key() -> str:
    """Mints a fresh, isolated admin (owner-role) key for this test session via the
    out-of-band bootstrap script, rather than reusing a real operator's key."""
    username = f"pytest-admin-{uuid.uuid4().hex[:8]}"
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "lara-gateway",
            "python",
            "-m",
            "database.seed.bootstrap_owner",
            "--username",
            username,
            "--display-name",
            "Pytest Admin",
            "--label",
            "pytest-session",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(Path(__file__).parent),
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("lara_"):
            return line
    raise RuntimeError(f"could not parse bootstrap output:\n{result.stdout}\n{result.stderr}")


@pytest.fixture()
def client(base_url: str) -> httpx.Client:
    with httpx.Client(base_url=base_url, timeout=10.0) as c:
        yield c


def create_user(client: httpx.Client, admin_key: str, *, role: str = "member") -> dict:
    username = f"pytest-user-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={"username": username, "display_name": username, "role": role},
    )
    resp.raise_for_status()
    return resp.json()


def issue_key(client: httpx.Client, admin_key: str, user_id: str, label: str = "pytest") -> dict:
    resp = client.post(
        f"/admin/users/{user_id}/api-keys",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={"label": label},
    )
    resp.raise_for_status()
    return resp.json()
