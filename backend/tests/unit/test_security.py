"""Password hashing, access tokens and the JWT-secret rule (ADR-015). No database."""

import base64
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
import pytest
from pydantic import ValidationError

from app.core.config import MIN_JWT_SECRET_BYTES, Settings, get_settings
from app.core.security import (
    DUMMY_HASH,
    ISSUER,
    InvalidTokenError,
    PasswordTooLongError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.governance import User
from tests.conftest import TEST_JWT_SECRET

# Throw-away values generated for this run; nothing here is a real credential.
PASSWORD = secrets.token_urlsafe(12)
OTHER_PASSWORD = secrets.token_urlsafe(12)


def _user(role: str = "ANALYST") -> User:
    return User(id=7, username="analyst", password_hash="x", role=role, is_active=True)


def _signed(claims: dict[str, Any], key: str = TEST_JWT_SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(claims, key, algorithm=algorithm)


def _claims(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": "7",
        "username": "analyst",
        "role": "ANALYST",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "jti": secrets.token_hex(16),
        "iss": ISSUER,
    }
    claims.update(overrides)
    return claims


# --- passwords ---


def test_hash_then_verify_true_and_wrong_password_false() -> None:
    hashed = hash_password(PASSWORD)
    assert hashed != PASSWORD and PASSWORD not in hashed
    assert hashed.startswith("$2b$12$")  # bcrypt, cost factor 12
    assert verify_password(PASSWORD, hashed) is True
    assert verify_password(OTHER_PASSWORD, hashed) is False


def test_hashing_twice_gives_different_salts() -> None:
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_more_than_72_bytes_is_rejected_not_truncated() -> None:
    with pytest.raises(PasswordTooLongError):
        hash_password("a" * 73)
    assert len(hash_password("a" * 72)) == 60  # exactly 72 bytes is fine
    with pytest.raises(PasswordTooLongError):
        hash_password("\u00e9" * 37)  # 74 bytes in UTF-8, though only 37 characters


def test_over_long_password_never_verifies_against_a_prefix() -> None:
    hashed = hash_password("a" * 72)
    assert verify_password("a" * 72 + "b", hashed) is False  # bcrypt alone would say True


def test_malformed_hash_is_false_not_an_error() -> None:
    assert verify_password(PASSWORD, "not-a-bcrypt-hash") is False


def test_dummy_hash_is_a_valid_cost_12_bcrypt_hash_nobody_can_match() -> None:
    """DUMMY_HASH is generated at import (no literal in source), cost 12 like real hashes."""
    assert re.fullmatch(r"\$2b\$12\$[./A-Za-z0-9]{53}", DUMMY_HASH)
    assert bcrypt.checkpw(b"probe", DUMMY_HASH.encode()) is False  # well-formed: bcrypt accepts it
    for candidate in (PASSWORD, "", "password", "a" * 72):
        assert verify_password(candidate, DUMMY_HASH) is False


# --- tokens ---


def test_token_round_trip_has_the_required_claims() -> None:
    token, expires_in = create_access_token(_user())
    claims = decode_access_token(token)
    assert expires_in == get_settings().access_token_minutes * 60 == 3600
    assert claims["sub"] == "7" and claims["username"] == "analyst"
    assert claims["role"] == "ANALYST" and claims["iss"] == "smartstock-backend"
    assert len(claims["jti"]) == 32 and int(claims["jti"], 16) >= 0
    assert claims["exp"] - claims["iat"] == expires_in


def test_every_token_has_a_unique_jti() -> None:
    first, second = create_access_token(_user())[0], create_access_token(_user())[0]
    assert decode_access_token(first)["jti"] != decode_access_token(second)["jti"]


def test_header_is_hs256() -> None:
    token, _ = create_access_token(_user())
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_expired_token_is_rejected() -> None:
    past = datetime.now(UTC) - timedelta(hours=2)
    token = _signed(_claims(iat=past, exp=past + timedelta(minutes=5)))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_tampered_signature_is_rejected() -> None:
    token, _ = create_access_token(_user())
    head, body, signature = token.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{head}.{body}.{flipped}")


def test_tampered_payload_is_rejected() -> None:
    token, _ = create_access_token(_user("ANALYST"))
    head, body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    payload["role"] = "ADMIN"
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{head}.{forged}.{signature}")


def test_token_signed_with_another_secret_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(_signed(_claims(), key=secrets.token_hex(32)))


def test_wrong_issuer_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(_signed(_claims(iss="someone-else")))


def test_alg_none_is_rejected() -> None:
    def segment(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    claims = _claims(
        iat=int(datetime.now(UTC).timestamp()), exp=int(datetime.now(UTC).timestamp()) + 300
    )
    unsigned = f"{segment({'alg': 'none', 'typ': 'JWT'})}.{segment(claims)}."
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned)


def test_hs512_token_is_rejected_even_with_the_right_secret() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(_signed(_claims(), algorithm="HS512"))


@pytest.mark.parametrize("missing", ["sub", "username", "role", "iat", "exp", "jti", "iss"])
def test_a_token_missing_any_required_claim_is_rejected(missing: str) -> None:
    claims = _claims()
    del claims[missing]
    with pytest.raises(InvalidTokenError):
        decode_access_token(_signed(claims))


@pytest.mark.parametrize("junk", ["", "abc", "a.b.c", "Bearer x", "\u00e9.\u00e9.\u00e9"])
def test_garbage_is_rejected_with_our_exception(junk: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(junk)


def test_the_error_never_contains_the_token() -> None:
    token = _signed(_claims(iss="someone-else"))
    with pytest.raises(InvalidTokenError) as caught:
        decode_access_token(token)
    assert token not in str(caught.value) and token not in repr(caught.value)


# --- settings: JWT secret and related limits ---


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "postgres_password": "x",
        "jwt_secret": TEST_JWT_SECRET,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_a_jwt_secret_under_32_bytes_stops_startup_with_a_clear_message() -> None:
    short = "s" * (MIN_JWT_SECRET_BYTES - 1)
    with pytest.raises(ValidationError) as caught:
        _settings(jwt_secret=short)
    assert "at least 32 bytes" in str(caught.value)
    assert short not in str(caught.value)  # the rejected value is not echoed


def test_a_32_byte_secret_is_accepted_and_bytes_not_characters_count() -> None:
    assert _settings(jwt_secret="s" * 32).jwt_secret.get_secret_value() == "s" * 32
    with pytest.raises(ValidationError):
        _settings(jwt_secret="\u00e9" * 15)  # 15 characters but 30 bytes


def test_only_hs256_is_accepted() -> None:
    assert _settings().jwt_algorithm == "HS256"
    for other in ("HS512", "none", "RS256"):
        with pytest.raises(ValidationError):
            _settings(jwt_algorithm=other)


@pytest.mark.parametrize(("minutes", "ok"), [(4, False), (5, True), (480, True), (481, False)])
def test_access_token_minutes_range(minutes: int, ok: bool) -> None:
    if ok:
        assert _settings(access_token_minutes=minutes).access_token_minutes == minutes
    else:
        with pytest.raises(ValidationError):
            _settings(access_token_minutes=minutes)


def test_defaults_match_the_prompt() -> None:
    settings = _settings()
    assert (settings.access_token_minutes, settings.login_max_failures) == (60, 5)
    assert (settings.login_lock_minutes, settings.max_request_bytes) == (15, 1_048_576)


def test_seed_user_passwords_are_optional_and_secret() -> None:
    settings = _settings(seed_user_password_admin="a-throwaway-value-123")
    assert settings.seed_user_password_manager is None
    assert "a-throwaway-value-123" not in repr(settings)
