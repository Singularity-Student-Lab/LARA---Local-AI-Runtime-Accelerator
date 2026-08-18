"""T-S3-11 (/v1/models returns aliases) and T-S3-14 (unknown alias)."""


def test_v1_models_returns_aliases_not_backend_ids(client, admin_key):
    resp = client.get("/v1/models", headers={"Authorization": f"Bearer {admin_key}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    ids = [m["id"] for m in data]
    assert "campus-coder" in ids
    # The real backend model id must never leak through this endpoint.
    assert "llama3:8b-instruct-q4_K_M" not in ids


def test_unknown_alias_returns_404_with_valid_list(client, admin_key):
    resp = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={"model": "does-not-exist", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error"]["type"] == "unknown_model"
    assert "campus-coder" in body["detail"]["error"]["message"]


def test_oversized_request_rejected_413(client, admin_key):
    huge = "x" * (3 * 1024 * 1024)  # exceeds default LARA_MAX_REQUEST_BYTES of 2MB
    resp = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {admin_key}"},
        json={"model": "campus-coder", "messages": [{"role": "user", "content": huge}]},
    )
    assert resp.status_code == 413
