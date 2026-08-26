"""Blueprint Testing table T-S5-01, T-S5-04, T-S5-10 through T-S5-13 (the subset testable
without a second real model or a live GPU in-container - see docs/architecture/modes.md)."""

import uuid

from tests.integration.conftest import create_user, issue_key


def test_default_mode_is_serving(client, admin_key):
    resp = client.get("/admin/mode", headers={"Authorization": f"Bearer {admin_key}"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "SERVING"


def test_mode_switch_and_audit(client, admin_key):
    switch = client.post(
        "/admin/mode", headers={"Authorization": f"Bearer {admin_key}"}, json={"mode": "GAMEDEV"}
    )
    assert switch.status_code == 200
    assert switch.json()["mode"] == "GAMEDEV"

    read_back = client.get("/admin/mode", headers={"Authorization": f"Bearer {admin_key}"})
    assert read_back.json()["mode"] == "GAMEDEV"
    assert read_back.json()["policy"]["pressure_policy_enabled"] is True

    # restore
    client.post("/admin/mode", headers={"Authorization": f"Bearer {admin_key}"}, json={"mode": "SERVING"})


def test_unknown_mode_rejected(client, admin_key):
    resp = client.post("/admin/mode", headers={"Authorization": f"Bearer {admin_key}"}, json={"mode": "BOGUS"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["type"] == "unknown_mode"


def test_non_admin_cannot_change_mode(client, admin_key):
    user = create_user(client, admin_key)
    key = issue_key(client, admin_key, user["id"])
    resp = client.post(
        "/admin/mode", headers={"Authorization": f"Bearer {key['api_key']}"}, json={"mode": "GAMEDEV"}
    )
    assert resp.status_code == 403


def test_status_reflects_effective_ceiling_without_prior_traffic(client, admin_key):
    """Regression test for a real bug: /status used to read scheduler.max_active_jobs
    directly, which only updated as a side effect of the last chat request - so a mode
    switch with no traffic since would report a stale ceiling. Fixed by computing the
    effective policy independently in /status (gateway/app/monitoring/status.py)."""
    client.post("/admin/mode", headers={"Authorization": f"Bearer {admin_key}"}, json={"mode": "GAMEDEV"})
    try:
        status = client.get("/status", headers={"Authorization": f"Bearer {admin_key}"})
        assert status.status_code == 200
        body = status.json()
        assert body["mode"] == "GAMEDEV"
        # This dev container has no GPU passthrough, so pressure fails safe to MODERATE
        # (see gateway/app/modes/pressure.py), which GAMEDEV's policy reduces the ceiling for.
        assert body["pressure_level"] == "MODERATE"
        assert body["effective_ceiling"] < 3
    finally:
        client.post("/admin/mode", headers={"Authorization": f"Bearer {admin_key}"}, json={"mode": "SERVING"})


def test_admin_models_registry_crud(client, admin_key):
    listing = client.get("/admin/models", headers={"Authorization": f"Bearer {admin_key}"})
    assert listing.status_code == 200
    aliases = [m["alias"] for m in listing.json()]
    assert "campus-coder" in aliases

    alias = f"test-alias-crud-{uuid.uuid4().hex[:8]}"
    create = client.post(
        "/admin/models",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={
            "alias": alias,
            "backend_name": "ollama-dev",
            "model_ref": "llama3:8b-instruct-q4_K_M",
            "context_limit": 4096,
            "enabled": True,
        },
    )
    assert create.status_code == 201

    disable = client.patch(
        f"/admin/models/{alias}",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={"enabled": False},
    )
    assert disable.status_code == 200
    assert disable.json()["enabled"] is False

    # A disabled alias must not be resolvable through the public surface.
    chat = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={"model": alias, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert chat.status_code == 404


def test_duplicate_alias_rejected(client, admin_key):
    dup = client.post(
        "/admin/models",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={
            "alias": "campus-coder",
            "backend_name": "ollama-dev",
            "model_ref": "llama3:8b-instruct-q4_K_M",
            "context_limit": 4096,
        },
    )
    assert dup.status_code == 409
