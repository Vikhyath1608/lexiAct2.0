"""tests/unit/test_security.py"""
import pytest
from app.core.security import (
    hash_password, verify_password,
    create_access_token, decode_access_token,
    create_refresh_token, hash_token,
    generate_otp, generate_reset_token,
)


def test_password_hash_and_verify():
    hashed = hash_password("mysecret123")
    assert hashed != "mysecret123"
    assert verify_password("mysecret123", hashed)


def test_wrong_password_rejected():
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_access_token_create_and_decode():
    token = create_access_token(42)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_invalid_token_returns_none():
    assert decode_access_token("invalid.token.here") is None


def test_tampered_token_rejected():
    token = create_access_token(1)
    tampered = token[:-5] + "XXXXX"
    assert decode_access_token(tampered) is None


def test_refresh_token_is_random():
    t1 = create_refresh_token()
    t2 = create_refresh_token()
    assert t1 != t2
    assert len(t1) > 32


def test_hash_token_is_deterministic():
    token = "some-refresh-token"
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != hash_token("other-token")


def test_otp_is_6_digits():
    for _ in range(20):
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()
        assert 100000 <= int(otp) <= 999999


def test_reset_token_is_url_safe():
    import re
    token = generate_reset_token()
    assert len(token) >= 32
    assert re.match(r'^[A-Za-z0-9_\-]+$', token)
