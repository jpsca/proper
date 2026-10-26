"""`app.dumps(..., timed=False)`: deterministic tokens that cannot expire.
Also `app.loads()` of timed tokens that are signed but malformed."""

import hashlib
import time

import itsdangerous
import pytest
from itsdangerous.encoding import base64_encode, int_to_bytes

from proper import App
from proper.helpers import jsonplus


KEY_A = "a" * 50
KEY_B = "b" * 50


def make_app(*keys):
    return App(__name__, {"SECRET_KEYS": list(keys)})


def reference(key, salt="x"):
    """itsdangerous' untimed serializer and signer with the settings of
    Proper's tokens, to make tokens with any payload."""
    kwargs = {"key_derivation": "hmac", "digest_method": hashlib.sha256}
    serializer = itsdangerous.URLSafeSerializer(key, salt=salt, serializer=jsonplus,
                                                signer_kwargs=kwargs)
    return serializer, serializer.make_signer(salt)


def test_untimed_tokens_are_deterministic():
    app = make_app(KEY_A)
    assert app.dumps({"id": 1}, salt="x", timed=False) == app.dumps({"id": 1}, salt="x", timed=False)
    assert app.loads(app.dumps({"id": 1}, salt="x", timed=False), salt="x", timed=False) == {"id": 1}


def test_untimed_tokens_depend_on_value_salt_and_key():
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x", timed=False)
    assert token != app.dumps({"id": 2}, salt="x", timed=False)
    assert token != app.dumps({"id": 1}, salt="y", timed=False)
    assert token != make_app(KEY_B).dumps({"id": 1}, salt="x", timed=False)


def test_untimed_loads_rejects_a_wrong_salt_or_a_tampered_token():
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x", timed=False)
    assert app.loads(token, salt="other", timed=False) is None
    assert app.loads(token[:-2] + "zz", salt="x", timed=False) is None
    assert app.loads("garbage", salt="x", timed=False) is None


def test_untimed_loads_tries_every_secret_key():
    token = make_app(KEY_A).dumps({"id": 1}, salt="x", timed=False)
    assert make_app(KEY_B, KEY_A).loads(token, salt="x", timed=False) == {"id": 1}
    assert make_app(KEY_B).loads(token, salt="x", timed=False) is None


def test_the_two_kinds_of_token_are_not_interchangeable():
    app = make_app(KEY_A)
    timed = app.dumps({"id": 1}, salt="x")
    untimed = app.dumps({"id": 1}, salt="x", timed=False)
    assert timed != untimed
    assert app.loads(untimed, salt="x") is None
    assert app.loads(timed, salt="x", timed=False) is None


def timed_token_with_a_compressed_payload(app, size_mod_4):
    """A timed token whose payload is compressed (starts with `.`) and has,
    after that `.`, a length of `size_mod_4` modulo 4, and its value."""
    for length in range(100, 400):
        value = {"v": "ab" * length}
        token = app.dumps(value, salt="x")
        payload = token.rsplit(".", 2)[0]
        if payload.startswith(".") and len(payload[1:]) % 4 == size_mod_4:
            return token, value
    raise AssertionError("no such token")  # pragma: no cover


@pytest.mark.parametrize("size_mod_4", [0, 2, 3])
def test_untimed_loads_refuses_a_timed_token_with_a_compressed_payload(size_mod_4):
    # A timed token is `payload.timestamp.signature`, signed over
    # `payload.timestamp` with the same key and salt. With a length of
    # 2 modulo 4, `payload.timestamp` decoded as base64 gave the zlib data
    # and the timestamp's bytes after it, which zlib ignored: the timed
    # token loaded as an untimed one, and never expired.
    app = make_app(KEY_A)
    token, value = timed_token_with_a_compressed_payload(app, size_mod_4)
    assert app.loads(token, salt="x") == value
    assert app.loads(token, salt="x", timed=False) is None


def test_untimed_loads_refuses_a_payload_with_a_dot_after_its_first_character():
    app = make_app(KEY_A)
    serializer, signer = reference(KEY_A)
    payload = serializer.dump_payload({"id": 1})
    assert app.loads(signer.sign(payload).decode(), salt="x", timed=False) == {"id": 1}
    for bad in (
        payload + b".AAAA",
        b"." + payload + b".AAAA",
        payload[:2] + b"." + payload[2:],
    ):
        assert app.loads(signer.sign(bad).decode(), salt="x", timed=False) is None


def test_no_token_loads_as_the_other_kind():
    app = make_app(KEY_A)
    for length in range(0, 600, 3):
        # Short values are not compressed; long, repetitive ones are.
        value = {"v": "ab" * length}
        timed = app.dumps(value, salt="x")
        untimed = app.dumps(value, salt="x", timed=False)
        assert app.loads(timed, salt="x") == value
        assert app.loads(untimed, salt="x", timed=False) == value
        assert app.loads(timed, salt="x", timed=False) is None
        assert app.loads(untimed, salt="x") is None


def test_timed_is_still_the_default():
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x")
    assert app.loads(token, salt="x", max_age=60) == {"id": 1}
    value, timestamp = app.loads(token, salt="x", return_timestamp=True)
    assert value == {"id": 1} and timestamp is not None


@pytest.mark.parametrize("kwargs", [{"max_age": 60}, {"return_timestamp": True}])
def test_untimed_loads_refuses_options_that_need_a_timestamp(kwargs):
    app = make_app(KEY_A)
    token = app.dumps({"id": 1}, salt="x", timed=False)
    with pytest.raises(ValueError, match="no timestamp"):
        app.loads(token, salt="x", timed=False, **kwargs)


def test_dumps_signs_with_the_newest_key():
    """Keys are listed oldest to newest; rotating means appending. What the
    app signs must be readable by an app that has dropped the oldest key."""
    rotated = make_app(KEY_A, KEY_B)
    for kwargs in ({}, {"timed": False}):
        token = rotated.dumps({"id": 1}, salt="x", **kwargs)
        assert make_app(KEY_B).loads(token, salt="x", **kwargs) == {"id": 1}
        assert make_app(KEY_A).loads(token, salt="x", **kwargs) is None


# The last second of year 9999, the largest timestamp a `datetime` can hold
MAX_TIMESTAMP = 253402300799


def sign_raw(app, payload, timestamp, salt="x"):
    """Sign `payload` and `timestamp` with the newest key, as `app.dumps()`
    does, but with any payload bytes and any timestamp."""
    _, signer = reference(app.config.SECRET_KEYS[-1], salt)
    value = payload + b"." + base64_encode(int_to_bytes(timestamp))
    return signer.sign(value).decode()


def test_sign_raw_makes_tokens_that_loads_accepts():
    app = make_app(KEY_A)
    payload = reference(KEY_A)[0].dump_payload({"id": 1})
    assert app.loads(sign_raw(app, payload, int(time.time())), salt="x") == {"id": 1}
    assert app.loads(sign_raw(app, payload, MAX_TIMESTAMP), salt="x") == {"id": 1}


@pytest.mark.parametrize(
    "payload, step",
    [
        (base64_encode(b"not json"), "unserializing"),
        (base64_encode(b"\xff\xfe"), "unserializing"),
        # itsdangerous drops the characters outside the base64 alphabet, so
        # `!!!` is an empty payload: a JSON error, not a base64 one.
        (b"!!!", "unserializing"),
        # Five characters can't be base64 (a length of 4n + 1).
        (b"abcde", "base64 decode"),
        (b".not-zlib", "zlib decompress"),
    ],
)
def test_loads_rejects_a_signed_payload_that_does_not_decode(payload, step):
    app = make_app(KEY_B, KEY_A)
    # The payload fails at the step the case is for.
    with pytest.raises(itsdangerous.BadPayload, match=step):
        reference(KEY_A)[0].load_payload(payload)
    token = sign_raw(app, payload, int(time.time()))
    assert app.loads(token, salt="x") is None
    assert app.loads(token, salt="x", max_age=60) is None
    assert app.loads(token, salt="x", return_timestamp=True) is None


@pytest.mark.parametrize("timestamp", [MAX_TIMESTAMP + 1, 2**64 - 1])
@pytest.mark.parametrize("kwargs", [{}, {"max_age": 60}])
def test_loads_rejects_a_signed_timestamp_after_year_9999(timestamp, kwargs):
    app = make_app(KEY_A)
    payload = reference(KEY_A)[0].dump_payload({"id": 1})
    token = sign_raw(app, payload, timestamp)
    assert app.loads(token, salt="x", **kwargs) is None
