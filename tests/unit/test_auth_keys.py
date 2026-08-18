"""Regression test for a real bug found via tests/integration: key_id/secret can themselves
contain "_" (secrets.token_urlsafe's alphabet includes it), which broke the original
underscore-delimited format. Fixed by using "." as the key_id/secret separator."""

from app.auth.keys import format_key, hash_secret, issue_key, parse_key, verify_secret


def test_roundtrip_issue_and_parse():
    key_id, secret, raw = issue_key()
    parsed = parse_key(raw)
    assert parsed == (key_id, secret)


def test_parse_handles_underscore_in_key_id_or_secret():
    """The exact bug: an id/secret containing "_" must not corrupt parsing."""
    raw = format_key("ab_cd_ef", "gh_ij_kl_mn")
    assert parse_key(raw) == ("ab_cd_ef", "gh_ij_kl_mn")


def test_parse_rejects_malformed_input():
    assert parse_key("not-a-key-at-all") is None
    assert parse_key("lara_") is None
    assert parse_key("lara_onlykeyid") is None
    assert parse_key("lara_.secretonly") is None
    assert parse_key("lara_keyidonly.") is None
    assert parse_key("") is None


def test_verify_secret_correct_and_incorrect():
    secret = "s3cret"
    pepper = "pepper1"
    h = hash_secret(secret, pepper)
    assert verify_secret(secret, h, pepper) is True
    assert verify_secret("wrong", h, pepper) is False
    assert verify_secret(secret, h, "different-pepper") is False


def test_issued_keys_are_unique():
    seen = set()
    for _ in range(200):
        key_id, _secret, _raw = issue_key()
        assert key_id not in seen
        seen.add(key_id)
