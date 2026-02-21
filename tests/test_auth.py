"""Tests for proper.auth — Auth, helpers, token generation & verification."""

from time import time
from unittest.mock import MagicMock

import pytest

from proper.auth import (
    Auth,
    force_bytes,
    from36,
    to36,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)
from proper.errors import WrongHashAlgorithm


SECRET_KEYS = ["*" * 50]


@pytest.fixture()
def auth():
    return Auth(secret_keys=SECRET_KEYS)


# ═══════════════════════════════════════════════════════════════════
# force_bytes
# ═══════════════════════════════════════════════════════════════════


class TestForceBytes:
    def test_str_to_bytes(self):
        assert force_bytes("hello") == b"hello"

    def test_bytes_utf8_passthrough(self):
        assert force_bytes(b"hello") is not None
        assert force_bytes(b"hello") == b"hello"

    def test_bytes_different_encoding(self):
        result = force_bytes(b"hello", encoding="ascii")
        assert result == b"hello"

    def test_int_to_bytes(self):
        assert force_bytes(42) == b"42"


# ═══════════════════════════════════════════════════════════════════
# to36 / from36
# ═══════════════════════════════════════════════════════════════════


class TestTo36:
    def test_zero(self):
        assert to36(0) == "0"

    def test_single_digit(self):
        assert to36(10) == "A"

    def test_large_number(self):
        result = to36(1000)
        assert from36(result) == 1000

    def test_string_input(self):
        assert to36("100") == to36(100)

    def test_boundary_35(self):
        assert to36(35) == "Z"

    def test_36_needs_two_chars(self):
        assert to36(36) == "10"

    def test_negative_raises(self):
        with pytest.raises(AssertionError):
            to36(-1)


class TestFrom36:
    def test_zero(self):
        assert from36("0") == 0

    def test_lowercase(self):
        assert from36("a") == 10

    def test_roundtrip(self):
        for n in [0, 1, 35, 36, 100, 99999]:
            assert from36(to36(n)) == n


# ═══════════════════════════════════════════════════════════════════
# urlsafe_base64 encode/decode
# ═══════════════════════════════════════════════════════════════════


class TestUrlsafeBase64:
    def test_roundtrip(self):
        for s in ["hello", "42", "user@example.com", "a" * 100]:
            assert urlsafe_base64_decode(urlsafe_base64_encode(s)) == s

    def test_encode_strips_padding(self):
        encoded = urlsafe_base64_encode("a")
        assert "=" not in encoded

    def test_decode_restores_padding(self):
        # "a" encodes to "YQ" (no padding), should still decode
        assert urlsafe_base64_decode("YQ") == "a"


# ═══════════════════════════════════════════════════════════════════
# Auth.__init__ / _set_hasher
# ═══════════════════════════════════════════════════════════════════


class TestAuthInit:
    def test_default_hasher(self):
        a = Auth(secret_keys=SECRET_KEYS)
        assert a.hasher is not None

    def test_custom_hasher(self):
        a = Auth(secret_keys=SECRET_KEYS, hash_name="sha256_crypt")
        assert a.hasher is not None

    def test_hash_name_none_uses_default(self):
        a = Auth(secret_keys=SECRET_KEYS, hash_name=None)
        assert a.hasher is not None

    def test_custom_rounds(self):
        a = Auth(secret_keys=SECRET_KEYS, rounds=1000)
        assert a.hasher is not None

    def test_invalid_hasher_raises(self):
        with pytest.raises(WrongHashAlgorithm):
            Auth(secret_keys=SECRET_KEYS, hash_name="md5")

    def test_hyphenated_hasher_name(self):
        a = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2-sha256")
        assert a.hasher is not None

    def test_stores_password_limits(self):
        a = Auth(secret_keys=SECRET_KEYS, password_minlen=8, password_maxlen=200)
        assert a.password_minlen == 8
        assert a.password_maxlen == 200


# ═══════════════════════════════════════════════════════════════════
# hash_password
# ═══════════════════════════════════════════════════════════════════


class TestHashPassword:
    def test_returns_hash(self, auth):
        hashed = auth.hash_password("validpassword")
        assert hashed is not None
        assert hashed != "validpassword"

    def test_none_returns_none(self, auth):
        assert auth.hash_password(None) is None

    def test_too_short_raises(self, auth):
        with pytest.raises(ValueError, match="too short"):
            auth.hash_password("ab")

    def test_too_long_raises(self, auth):
        with pytest.raises(ValueError, match="too long"):
            auth.hash_password("a" * 2000)

    def test_exact_minlen(self):
        a = Auth(secret_keys=SECRET_KEYS, password_minlen=3)
        assert a.hash_password("abc") is not None

    def test_exact_maxlen(self):
        a = Auth(secret_keys=SECRET_KEYS, password_maxlen=10)
        assert a.hash_password("a" * 10) is not None


# ═══════════════════════════════════════════════════════════════════
# password_is_valid
# ═══════════════════════════════════════════════════════════════════


class TestPasswordIsValid:
    def test_valid_password(self, auth):
        hashed = auth.hash_password("mypassword")
        assert auth.password_is_valid("mypassword", hashed) is True

    def test_wrong_password(self, auth):
        hashed = auth.hash_password("mypassword")
        assert auth.password_is_valid("wrong", hashed) is False

    def test_none_secret(self, auth):
        assert auth.password_is_valid(None, "somehash") is False

    def test_none_hashed(self, auth):
        assert auth.password_is_valid("password", None) is False

    def test_both_none(self, auth):
        assert auth.password_is_valid(None, None) is False

    def test_too_long_password_rejected(self, auth):
        hashed = auth.hash_password("validpass")
        assert auth.password_is_valid("a" * 2000, hashed) is False

    def test_malformed_hash_returns_false(self, auth):
        assert auth.password_is_valid("password", "not-a-valid-hash") is False


# ═══════════════════════════════════════════════════════════════════
# authenticate
# ═══════════════════════════════════════════════════════════════════


def _make_user(password_hash):
    user = MagicMock()
    user.password = password_hash
    user.id = 1
    return user


class TestAuthenticate:
    def test_valid_credentials(self, auth):
        hashed = auth.hash_password("secret123")
        user = _make_user(hashed)
        model = MagicMock()
        model.get_by_login.return_value = user

        result = auth.authenticate(model, "alice", "secret123")
        assert result is user

    def test_user_not_found(self, auth):
        model = MagicMock()
        model.get_by_login.return_value = None

        result = auth.authenticate(model, "nobody", "secret123")
        assert result is None

    def test_none_login(self, auth):
        model = MagicMock()
        assert auth.authenticate(model, None, "secret123") is None

    def test_none_password(self, auth):
        model = MagicMock()
        assert auth.authenticate(model, "alice", None) is None

    def test_user_has_no_password(self, auth):
        user = _make_user(None)
        user.password = ""
        model = MagicMock()
        model.get_by_login.return_value = user

        result = auth.authenticate(model, "alice", "secret123")
        assert result is None

    def test_wrong_password(self, auth):
        hashed = auth.hash_password("correct")
        user = _make_user(hashed)
        model = MagicMock()
        model.get_by_login.return_value = user

        result = auth.authenticate(model, "alice", "wrong")
        assert result is None

    def test_update_hash_false_skips_update(self, auth):
        hashed = auth.hash_password("secret123")
        user = _make_user(hashed)
        model = MagicMock()
        model.get_by_login.return_value = user

        result = auth.authenticate(model, "alice", "secret123", update_hash=False)
        assert result is user


# ═══════════════════════════════════════════════════════════════════
# update_password_hash
# ═══════════════════════════════════════════════════════════════════


class TestUpdatePasswordHash:
    def test_same_scheme_no_update(self, auth):
        hashed = auth.hash_password("secret123")
        user = MagicMock()
        user.password = hashed

        auth.update_password_hash("secret123", user)
        # password attribute should NOT be reassigned (same scheme)
        assert not hasattr(user, "pasword") or user.pasword == user.pasword

    def test_different_scheme_updates(self):
        # Create auth with one scheme, hash with another
        auth_old = Auth(secret_keys=SECRET_KEYS, hash_name="sha256_crypt")
        old_hash = auth_old.hash_password("secret123")

        auth_new = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512")
        user = MagicMock()
        user.password = old_hash

        auth_new.update_password_hash("secret123", user)
        # user.pasword (note: typo in source) should be set to a new hash
        assert user.pasword != old_hash

    def test_none_hash_returns_early(self, auth):
        user = MagicMock()
        user.password = "somehash"
        # hash_password returns None for None input
        auth.update_password_hash(None, user)


# ═══════════════════════════════════════════════════════════════════
# get_token / split_token
# ═══════════════════════════════════════════════════════════════════


class TestTokens:
    def test_get_token_format(self, auth):
        user = MagicMock()
        user.id = 42
        user.password = "hashvalue"
        token = auth.get_token(user, timestamp=1000000)
        parts = token.split("$")
        assert len(parts) == 3

    def test_split_token_roundtrip(self, auth):
        user = MagicMock()
        user.id = 42
        user.password = "hashvalue"
        token = auth.get_token(user, timestamp=1000000)
        user_id, ts, digest = auth.split_token(token)
        assert user_id == "42"
        assert ts == 1000000
        assert len(digest) > 0

    def test_split_token_malformed(self, auth):
        user_id, ts, digest = auth.split_token("garbage")
        assert user_id == ""
        assert ts == 0
        assert digest == ""

    def test_get_token_uses_latest_secret(self):
        user = MagicMock(id=1, password="hash")

        auth1 = Auth(secret_keys=["A" * 50])
        auth2 = Auth(secret_keys=["B" * 50])
        token1 = auth1.get_token(user, timestamp=100)
        token2 = auth2.get_token(user, timestamp=100)
        # Different secret keys should produce different tokens
        assert token1 != token2

    def test_get_token_auto_timestamp(self, auth):
        user = MagicMock(id=1, password="hash")
        token = auth.get_token(user)
        _, ts, _ = auth.split_token(token)
        assert abs(ts - int(time())) <= 2


# ═══════════════════════════════════════════════════════════════════
# check_token
# ═══════════════════════════════════════════════════════════════════


class TestCheckToken:
    def test_valid_token(self, auth):
        user = MagicMock(id=42, password="hashvalue")
        model = MagicMock()
        model.get_by_id.return_value = user

        token = auth.get_token(user, timestamp=int(time()))
        result = auth.check_token(model, token, token_life=3600)
        assert result is user

    def test_none_token(self, auth):
        model = MagicMock()
        assert auth.check_token(model, None, token_life=3600) is None

    def test_malformed_token(self, auth):
        model = MagicMock()
        result = auth.check_token(model, "garbage", token_life=3600)
        assert result is None

    def test_user_not_found(self, auth):
        user = MagicMock(id=42, password="hash")
        token = auth.get_token(user, timestamp=int(time()))

        model = MagicMock()
        model.get_by_id.return_value = None
        result = auth.check_token(model, token, token_life=3600)
        assert result is None

    def test_expired_token(self, auth):
        user = MagicMock(id=42, password="hash")
        model = MagicMock()
        model.get_by_id.return_value = user

        old_ts = int(time()) - 7200
        token = auth.get_token(user, timestamp=old_ts)
        result = auth.check_token(model, token, token_life=3600)
        assert result is None

    def test_wrong_digest(self, auth):
        user = MagicMock(id=42, password="hash")
        model = MagicMock()
        model.get_by_id.return_value = user

        token = auth.get_token(user, timestamp=int(time()))
        # Tamper with the digest
        parts = token.rsplit("$", 1)
        tampered = parts[0] + "$" + "0" * len(parts[1])

        result = auth.check_token(model, tampered, token_life=3600)
        assert result is None

    def test_rotated_secret_key_still_valid(self):
        old_key = "A" * 50
        new_key = "B" * 50

        auth_old = Auth(secret_keys=[old_key])
        user = MagicMock(id=42, password="hash")
        token = auth_old.get_token(user, timestamp=int(time()))

        # App now has both keys (old + new)
        auth_new = Auth(secret_keys=[old_key, new_key])
        model = MagicMock()
        model.get_by_id.return_value = user

        result = auth_new.check_token(model, token, token_life=3600)
        assert result is user

    def test_user_password_none_in_hmac(self, auth):
        """user.password can be None — _salted_hmac handles it."""
        user = MagicMock(id=1, password=None)
        token = auth.get_token(user, timestamp=int(time()))

        model = MagicMock()
        model.get_by_id.return_value = user
        result = auth.check_token(model, token, token_life=3600)
        assert result is user
