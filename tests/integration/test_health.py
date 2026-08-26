def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    # T-S3 content rule: minimal, no version/internals.
    assert "version" not in resp.text.lower()
