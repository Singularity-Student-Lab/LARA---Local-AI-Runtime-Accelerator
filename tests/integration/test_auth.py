"""Blueprint Testing table T-S3-01 through T-S3-10."""

from tests.integration.conftest import create_user, issue_key


def test_missing_header_401(client):
    resp = client.get("/v1/models")
    assert resp.status_code == 401


def test_malformed_key_401(client):
    resp = client.get("/v1/models", headers={"Authorization": "Bearer not-a-real-key"})
    assert resp.status_code == 401


def test_unknown_key_id_401(client):
    resp = client.get("/v1/models", headers={"Authorization": "Bearer lara_doesnotexist_secret"})
    assert resp.status_code == 401


def test_all_denial_bodies_identical_shape(client):
    """No user enumeration: missing/malformed/unknown-key-id/wrong-secret must be
    indistinguishable to the caller (blueprint section 3.4 point 5)."""
    bodies = []
    for headers in [
        {},
        {"Authorization": "Bearer garbage"},
        {"Authorization": "Bearer lara_doesnotexist_secret"},
    ]:
        resp = client.get("/v1/models", headers=headers)
        assert resp.status_code == 401
        bodies.append(resp.json())
    assert bodies[0] == bodies[1] == bodies[2]


def test_valid_key_allowed(client, admin_key):
    resp = client.get("/v1/models", headers={"Authorization": f"Bearer {admin_key}"})
    assert resp.status_code == 200
    assert resp.json()["object"] == "list"


def test_revoked_key_denied_immediately(client, admin_key):
    user = create_user(client, admin_key)
    key = issue_key(client, admin_key, user["id"])
    raw_key, key_id = key["api_key"], key["key_id"]

    ok = client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert ok.status_code == 200

    revoke = client.delete(f"/admin/api-keys/{key_id}", headers={"Authorization": f"Bearer {admin_key}"})
    assert revoke.status_code == 204

    denied = client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert denied.status_code == 401


def test_disabled_user_denied(client, admin_key):
    user = create_user(client, admin_key)
    key = issue_key(client, admin_key, user["id"])
    raw_key = key["api_key"]

    ok = client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert ok.status_code == 200

    patch = client.patch(
        f"/admin/users/{user['id']}",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={"enabled": False},
    )
    assert patch.status_code == 200

    denied = client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert denied.status_code == 403


def test_non_admin_cannot_reach_admin_endpoints(client, admin_key):
    user = create_user(client, admin_key, role="member")
    key = issue_key(client, admin_key, user["id"])
    resp = client.get("/admin/users", headers={"Authorization": f"Bearer {key['api_key']}"})
    assert resp.status_code == 403


def test_raw_key_never_appears_in_key_listing(client, admin_key):
    user = create_user(client, admin_key)
    key = issue_key(client, admin_key, user["id"])
    listing = client.get(
        f"/admin/users/{user['id']}/api-keys", headers={"Authorization": f"Bearer {admin_key}"}
    )
    assert listing.status_code == 200
    assert key["api_key"] not in listing.text
    secret = key["api_key"].split(".", 1)[1]  # the secret half specifically
    assert secret not in listing.text
