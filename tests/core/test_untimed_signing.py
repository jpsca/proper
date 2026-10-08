"""`app.dumps(..., timed=False)`: deterministic tokens that cannot expire.
Also `app.loads()` of timed tokens that are signed but malformed."""

import time

import itsdangerous
import pytest
from itsdangerous.encoding import base64_encode, int_to_bytes

from proper import App


KEY_A = "a" * 50
KEY_B = "b" * 50


def make_app(*keys):
    return App(__name__, {"SECRET_KEYS": list(keys)})


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
    signer = app.serializers[-1].make_signer(salt)
    value = payload + b"." + base64_encode(int_to_bytes(timestamp))
    return itsdangerous.Signer.sign(signer, value).decode()


def test_sign_raw_makes_tokens_that_loads_accepts():
    app = make_app(KEY_A)
    payload = app.serializers[-1].dump_payload({"id": 1})
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
        app.serializers[-1].load_payload(payload)
    token = sign_raw(app, payload, int(time.time()))
    assert app.loads(token, salt="x") is None
    assert app.loads(token, salt="x", max_age=60) is None
    assert app.loads(token, salt="x", return_timestamp=True) is None


@pytest.mark.parametrize("timestamp", [MAX_TIMESTAMP + 1, 2**64 - 1])
@pytest.mark.parametrize("kwargs", [{}, {"max_age": 60}, {"return_timestamp": True}])
def test_loads_rejects_a_signed_timestamp_after_year_9999(timestamp, kwargs):
    app = make_app(KEY_A)
    payload = app.serializers[-1].dump_payload({"id": 1})
    token = sign_raw(app, payload, timestamp)
    assert app.loads(token, salt="x", **kwargs) is None
