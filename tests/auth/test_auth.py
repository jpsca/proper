from unittest.mock import MagicMock

import passlib.hash
import peewee as pw
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

    @pytest.mark.parametrize(
        "password",
        [
            "contra\u00a0seña",  # non-breaking space
            "ｐａｓｓword",  # full-width letters
            "pass\u00adword",  # soft hyphen
        ],
    )
    def test_password_that_is_normalized(self, auth, password):
        """Regression: `hash_password` normalizes the password, so the check
        must do it too or the password that was set doesn't work."""
        hashed = auth.hash_password(password)
        assert auth.password_is_valid(password, hashed) is True

    def test_hash_of_a_password_without_normalizing(self, auth):
        password = "contra\u00a0seña"
        hashed = auth.hasher.hash(password)
        assert auth.password_is_valid(password, hashed) is True
        assert auth.password_is_valid("contra seña", hashed) is False

    def test_password_that_cannot_be_normalized(self, auth):
        password = "pass\u0007word"
        with pytest.raises(ValueError):
            auth.hash_password(password)
        hashed = auth.hasher.hash(password)
        assert auth.password_is_valid(password, hashed) is True
        assert auth.password_is_valid("pass\u0007wor", hashed) is False


class User(pw.Model):
    login = pw.CharField(unique=True)
    password = pw.CharField()

    @classmethod
    def get_by_login(cls, login):
        return cls.get_or_none(cls.login == login)


@pytest.fixture()
def db():
    database = pw.SqliteDatabase(":memory:")
    with database.bind_ctx([User]):
        database.create_tables([User])
        yield database
    database.close()


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

    def test_current_hash_is_not_saved(self, auth):
        hashed = auth.hash_password("secret123")
        user = _make_user(hashed)
        model = MagicMock()
        model.get_by_login.return_value = user

        auth.authenticate(model, "alice", "secret123")
        assert user.password == hashed
        user.save.assert_not_called()

    def test_outdated_hash_is_updated_and_saved(self, db):
        old_hash = passlib.hash.sha256_crypt.using(rounds=1000).hash("secret123")
        User.create(login="alice", password=old_hash)
        auth = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512", rounds=1000)

        assert auth.authenticate(User, "alice", "secret123") is not None

        new_hash = User.get_by_login("alice").password
        assert new_hash.startswith("$pbkdf2-sha512$1000$")
        # The new hash is the one checked from now on, and it is not replaced again
        assert auth.authenticate(User, "alice", "secret123") is not None
        assert User.get_by_login("alice").password == new_hash

    def test_wrong_password_does_not_update_the_hash(self, db):
        old_hash = passlib.hash.sha256_crypt.using(rounds=1000).hash("secret123")
        User.create(login="alice", password=old_hash)
        auth = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512", rounds=1000)

        assert auth.authenticate(User, "alice", "wrong") is None
        assert User.get_by_login("alice").password == old_hash

    def test_update_hash_false_skips_update(self, db):
        old_hash = passlib.hash.sha256_crypt.using(rounds=1000).hash("secret123")
        User.create(login="alice", password=old_hash)
        auth = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512", rounds=1000)

        user = auth.authenticate(User, "alice", "secret123", update_hash=False)
        assert user.password == old_hash
        assert User.get_by_login("alice").password == old_hash

    def test_password_shorter_than_the_minimum(self, db):
        """Regression: a password set when the minimum length was lower
        must keep working, with or without an outdated hash."""
        old_hash = passlib.hash.sha256_crypt.using(rounds=1000).hash("abc")
        User.create(login="alice", password=old_hash)
        auth = Auth(
            secret_keys=SECRET_KEYS,
            hash_name="pbkdf2_sha512",
            rounds=1000,
            password_minlen=8,
        )

        assert auth.authenticate(User, "alice", "abc") is not None
        new_hash = User.get_by_login("alice").password
        assert new_hash.startswith("$pbkdf2-sha512$1000$")

        assert auth.authenticate(User, "alice", "abc") is not None
        assert User.get_by_login("alice").password == new_hash


class FakeUser:
    def __init__(self, password):
        self.password = password


class TestUpdatePasswordHash:
    def test_same_settings_no_update(self, auth):
        hashed = auth.hash_password("secret123")
        user = FakeUser(hashed)

        assert auth.update_password_hash("secret123", user) is False
        assert user.password == hashed

    def test_does_not_hash_when_there_is_nothing_to_update(self, auth):
        user = FakeUser(auth.hash_password("secret123"))
        auth.hasher = MagicMock(wraps=auth.hasher)

        auth.update_password_hash("secret123", user)
        auth.hasher.hash.assert_not_called()

    def test_different_scheme_updates(self):
        old_hash = passlib.hash.sha256_crypt.using(rounds=1000).hash("secret123")
        auth = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512", rounds=1000)
        user = FakeUser(old_hash)

        assert auth.update_password_hash("secret123", user) is True
        assert user.password.startswith("$pbkdf2-sha512$1000$")
        assert auth.password_is_valid("secret123", user.password)
        # Regression: it must set `user.password`, not a misspelled attribute
        assert vars(user).keys() == {"password"}

    @pytest.mark.parametrize("rounds", [1000, 3000])
    def test_different_rounds_updates(self, rounds):
        old_hash = passlib.hash.pbkdf2_sha512.using(rounds=rounds).hash("secret123")
        auth = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512", rounds=2000)
        user = FakeUser(old_hash)

        assert auth.update_password_hash("secret123", user) is True
        assert user.password.startswith("$pbkdf2-sha512$2000$")

    def test_password_is_normalized(self):
        password = "contra\u00a0seña"
        old_hash = passlib.hash.sha256_crypt.using(rounds=1000).hash(password)
        auth = Auth(secret_keys=SECRET_KEYS, hash_name="pbkdf2_sha512", rounds=1000)
        user = FakeUser(old_hash)

        assert auth.update_password_hash(password, user) is True
        assert auth.hasher.verify("contra seña", user.password)

    def test_none_secret_returns_early(self, auth):
        user = FakeUser(passlib.hash.sha256_crypt.using(rounds=1000).hash("x"))
        original = user.password

        assert auth.update_password_hash(None, user) is False
        assert user.password == original

    @pytest.mark.parametrize("password", ["", None, "not-a-valid-hash"])
    def test_no_valid_hash_returns_early(self, auth, password):
        user = FakeUser(password)

        assert auth.update_password_hash("secret123", user) is False
        assert user.password == password
