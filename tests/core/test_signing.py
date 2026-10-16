"""`App.dumps` and `App.loads` make and read the tokens of itsdangerous
(`URLSafeTimedSerializer` and `URLSafeSerializer`, with HMAC-SHA256 key
derivation), with the native code: tokens made before keep working."""
import datetime
import hashlib
import logging
import os
import time
import zlib

import itsdangerous
import pytest
from itsdangerous.encoding import base64_encode

from proper import App, _native
from proper.errors import BadSignature, ConfigError
from proper.helpers import jsonplus


KEY_OLD = "o" * 50
KEY_NEW = "n" * 50
NOW = 1_760_000_000


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """The same second for Proper and itsdangerous."""
    monkeypatch.setattr(time, "time", lambda: NOW + 0.5)


def make_app(*keys):
    return App(__name__, {"SECRET_KEYS": list(keys)})


def reference(key, salt, *, timed=True):
    """itsdangerous with the settings of Proper's tokens."""
    cls = itsdangerous.URLSafeTimedSerializer if timed else itsdangerous.URLSafeSerializer
    return cls(key, salt=b"", serializer=jsonplus, signer_kwargs={
        "key_derivation": "hmac", "digest_method": hashlib.sha256,
    }), salt


VALUES = [
    {"id": 1},
    {"user": "ana", "nested": {"a": [1, 2, {"b": None}]}, "when": datetime.date(2026, 10, 15)},
    {"big": "x" * 2000},  # compressed: the payload starts with "."
    [1, "two", 3.0, True, None],
    "ñandú",
    None,
    0,
]


@pytest.mark.parametrize("obj", VALUES)
@pytest.mark.parametrize("salt", [None, "s"])
@pytest.mark.parametrize("timed", [True, False])
def test_the_tokens_of_itsdangerous(obj, salt, timed):
    app = make_app(KEY_OLD, KEY_NEW)
    serializer, salt_ = reference(KEY_NEW, salt, timed=timed)
    expected = serializer.dumps(obj, salt="" if salt is None else salt)
    token = app.dumps(obj, salt=salt, timed=timed)
    assert token == expected
    assert app.loads(token, salt=salt, timed=timed) == obj


@pytest.mark.parametrize("timed", [True, False])
def test_a_token_of_an_older_key(timed):
    serializer, _ = reference(KEY_OLD, "s", timed=timed)
    token = serializer.dumps({"id": 1}, salt="s")
    assert make_app(KEY_OLD, KEY_NEW).loads(token, salt="s", timed=timed) == {"id": 1}
    assert make_app(KEY_NEW).loads(token, salt="s", timed=timed) is None


def test_the_timestamp():
    app = make_app(KEY_NEW)
    value, signed_at = app.loads(app.dumps({"id": 1}, salt="s"), salt="s", return_timestamp=True)
    assert value == {"id": 1}
    assert signed_at == datetime.datetime.fromtimestamp(NOW, tz=datetime.UTC)


def test_bytes_are_read_as_text():
    app = make_app(KEY_NEW)
    assert app.loads(app.dumps({"id": 1}, salt="s").encode(), salt="s") == {"id": 1}


def signer(key, salt="s"):
    """itsdangerous' signer of Proper's tokens, to sign any bytes."""
    return itsdangerous.Signer(key, salt=salt, key_derivation="hmac",
                               digest_method=hashlib.sha256)


def sign(key, payload: bytes, timestamp: int, salt="s"):
    """A token over any payload and timestamp, signed as Proper signs."""
    ts = timestamp.to_bytes((timestamp.bit_length() + 7) // 8, "big")
    return signer(key, salt).sign(payload + b"." + base64_encode(ts)).decode()


GOOD_PAYLOAD = base64_encode(b'{"id": 1}')

REFUSED = {
    "another key": ("BadSignature", lambda: make_app(KEY_OLD).dumps({"id": 1}, salt="s")),
    "another salt": ("BadSignature", lambda: make_app(KEY_NEW).dumps({"id": 1}, salt="t")),
    "tampered payload": ("BadSignature", lambda: "x" + make_app(KEY_NEW).dumps(1, salt="s")[1:]),
    "tampered signature": ("BadSignature", lambda: make_app(KEY_NEW).dumps(1, salt="s")[:-2] + "AA"),
    "no dot": ("BadSignature", lambda: "garbage"),
    "a signature too long": ("BadSignature", lambda: "a.b." + "A" * 70),
    "empty": ("BadSignature", lambda: ""),
    "expired": ("SignatureExpired", lambda: sign(KEY_NEW, GOOD_PAYLOAD, NOW - 120)),
    "from the future": ("SignatureExpired", lambda: sign(KEY_NEW, GOOD_PAYLOAD, NOW + 120)),
    "after year 9999": ("BadData", lambda: sign(KEY_NEW, GOOD_PAYLOAD, 253402300800)),
    "a timestamp of 9 bytes": ("BadData", lambda: sign(KEY_NEW, GOOD_PAYLOAD, 2**64)),
    "no timestamp": ("BadData", lambda: signer(KEY_NEW).sign(GOOD_PAYLOAD).decode()),
    "timestamp not base64": ("BadData", lambda: signer(KEY_NEW).sign(GOOD_PAYLOAD + b".abcde")
                             .decode()),
    "payload not base64": ("BadData", lambda: sign(KEY_NEW, b"abcde", NOW)),
    "payload not json": ("BadData", lambda: sign(KEY_NEW, base64_encode(b"{nope"), NOW)),
    "payload not utf-8": ("BadData", lambda: sign(KEY_NEW, base64_encode(b"\xff\xfe"), NOW)),
    "payload not zlib": ("BadData", lambda: sign(KEY_NEW, b"." + base64_encode(b"not zlib"), NOW)),
    "compressed payload not base64": ("BadData", lambda: sign(KEY_NEW, b".abcde", NOW)),
}


@pytest.mark.parametrize("case", REFUSED)
def test_what_is_refused_and_why(case, caplog):
    reason, make = REFUSED[case]
    token = make()
    serializer, _ = reference(KEY_NEW, "s")
    # itsdangerous refuses it too (a timestamp after 9999 with `ValueError`)
    with pytest.raises((itsdangerous.BadData, ValueError)):
        serializer.loads(token, salt="s", max_age=60)
    app = make_app(KEY_NEW)
    with caplog.at_level(logging.DEBUG, logger="proper"):
        assert app.loads(token, salt="s", max_age=60) is None
    assert reason in caplog.text


def test_a_truncated_zlib_stream_is_refused():
    data = zlib.compress(b'{"v": "' + b"ab" * 5000 + b'"}')
    token = sign(KEY_NEW, b"." + base64_encode(data[: len(data) // 2]), NOW)
    assert make_app(KEY_NEW).loads(token, salt="s") is None


def test_without_max_age_an_old_token_is_read():
    token = sign(KEY_NEW, GOOD_PAYLOAD, NOW - 10**6)
    assert make_app(KEY_NEW).loads(token, salt="s") == {"id": 1}


def test_a_negative_max_age_refuses_every_token(caplog):
    app = make_app(KEY_NEW)
    with caplog.at_level(logging.DEBUG, logger="proper"):
        assert app.loads(app.dumps({"id": 1}, salt="s"), salt="s", max_age=-1) is None
    assert "SignatureExpired" in caplog.text


@pytest.mark.parametrize("value", [
    {"x": os.urandom(_native.BUFFER_SIZE).hex()},  # random hex: it hardly compresses
    {"x": "ab" * _native.BUFFER_SIZE},  # compresses to a few hundred bytes
])
def test_a_payload_larger_than_the_buffers(value):
    app = make_app(KEY_NEW)
    assert app.loads(app.dumps(value, salt="s"), salt="s") == value


def test_the_keys_are_prepared_once_per_salt():
    app = make_app(KEY_OLD, KEY_NEW)
    app.loads(app.dumps(1, salt="s"), salt="s")
    signing = app._signings["s"]
    app.loads(app.dumps(2, salt="s"), salt="s")
    assert app._signings["s"] is signing
    assert signing.count == 2


def test_new_secret_keys_forget_the_derived_ones():
    app = make_app(KEY_OLD)
    token = app.dumps(1, salt="s")
    app.config.SECRET_KEYS = [KEY_NEW]
    app._setup_signing()
    assert app._signings == {}
    assert app.loads(token, salt="s") is None


def test_secret_keys_as_bytes():
    app = make_app(KEY_NEW.encode())
    assert app.dumps(1, salt="s") == make_app(KEY_NEW).dumps(1, salt="s")


def test_bad_signature_keeps_its_message_and_payload():
    error = BadSignature("tampered", payload=b"data")
    assert isinstance(error, ConfigError)
    assert (error.message, error.payload) == ("tampered", b"data")
    assert BadSignature().message == "Bad signature"
