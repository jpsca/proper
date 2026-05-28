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


class TestUpdatePasswordHash:
    def test_same_scheme_no_update(self, auth):
        hashed = auth.hash_password("secret123")
        user = MagicMock()
        user.password = hashed
        original = user.password

        auth.update_password_hash("secret123", user)
        # Same scheme → password should not be reassigned
        assert user.password == original

    def test_different_scheme_updates(self):
        # Create auth with one scheme, hash with another
        auth_old = Auth(secret_keys=SECRET_KEYS, hash_name="sha256_crypt")
        old_hash = auth_old.hash_password("secret123")

        auth_new = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512")
        user = MagicMock()
        user.password = old_hash

        auth_new.update_password_hash("secret123", user)
        # password should be updated to the new scheme
        assert user.password != old_hash
        assert user.password.startswith("$pbkdf2-sha512$")

    def test_different_scheme_sets_password_not_typo(self):
        """Regression: update_password_hash must set user.password,
        not a misspelled attribute like user.pasword."""
        auth_old = Auth(secret_keys=SECRET_KEYS, hash_name="sha256_crypt")
        old_hash = auth_old.hash_password("secret123")

        auth_new = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512")

        class FakeUser:
            def __init__(self, password):
                self.password = password

        user = FakeUser(old_hash)
        auth_new.update_password_hash("secret123", user)

        # The correct attribute was updated
        assert user.password != old_hash
        assert user.password.startswith("$pbkdf2-sha512$")
        # No misspelled attribute was created
        assert not hasattr(user, "pasword")

    def test_none_hash_returns_early(self, auth):
        user = MagicMock()
        user.password = "somehash"
        original = user.password
        # hash_password returns None for None input
        auth.update_password_hash(None, user)
        assert user.password == original
