"""`App._quick_loads`: `loads` of a good timed token without the serializers.

It must never accept what the serializers refuse, and must give the same
value for what they accept. What it can't vouch for, `loads` sends to them.
"""
import datetime
import hashlib
import time

import itsdangerous
import pytest
from itsdangerous.encoding import base64_encode, int_to_bytes

from proper import App
from proper.app import _UNSURE


KEY_OLD = "o" * 50
KEY_NEW = "n" * 50


def make_app(*keys):
    return App(__name__, {"SECRET_KEYS": list(keys)})


def by_the_serializers(app, token, *, max_age=None, salt=None):
    """What `loads` answered before `_quick_loads`: the first serializer
    that accepts the token, or `None`."""
    for serializer in app.serializers:
        try:
            return serializer.loads(token, max_age=max_age, salt=salt)
        except itsdangerous.BadData, ValueError, OverflowError, OSError:
            pass
    return None


def sign(key, payload: bytes, timestamp: int, salt="s"):
    """A token over any payload and timestamp, signed as the serializers do."""
    signer = itsdangerous.URLSafeTimedSerializer(
        key, signer_kwargs={"key_derivation": "hmac", "digest_method": hashlib.sha256}
    ).make_signer(salt)
    body = payload + b"." + base64_encode(int_to_bytes(timestamp))
    return (body + b"." + signer.get_signature(body)).decode()


GOOD = [
    {"id": 1},
    {"user": "ana", "nested": {"a": [1, 2, {"b": None}]}, "when": datetime.date(2026, 10, 15)},
    {"big": "x" * 2000},  # compressed: the payload starts with "."
    [1, "two", 3.0, True, None],
    "a string",
    None,
]


@pytest.mark.parametrize("obj", GOOD)
@pytest.mark.parametrize("salt", [None, "s"])
def test_a_good_token_is_read_as_the_serializers_read_it(obj, salt):
    app = make_app(KEY_NEW)
    token = app.dumps(obj, salt=salt)
    assert app._quick_loads(token, None, salt) == by_the_serializers(app, token, salt=salt)
    assert app._quick_loads(token, 60, salt) == obj
    assert app.loads(token, salt=salt, max_age=60) == obj


def test_a_compressed_payload_is_vouched_for():
    app = make_app(KEY_NEW)
    token = app.dumps({"big": "x" * 2000}, salt="s")
    assert token.startswith(".")
    assert app._quick_loads(token, None, "s") == {"big": "x" * 2000}


def test_a_token_of_an_older_key():
    old = make_app(KEY_OLD).dumps({"id": 1}, salt="s")
    app = make_app(KEY_OLD, KEY_NEW)
    assert app._quick_loads(old, None, "s") == {"id": 1}
    assert app._quick_loads(app.dumps({"id": 2}, salt="s"), None, "s") == {"id": 2}


def test_the_keys_are_derived_once_per_salt():
    app = make_app(KEY_OLD, KEY_NEW)
    app.loads(app.dumps(1, salt="s"), salt="s")
    unsigners = app._unsigners["s"]
    app.loads(app.dumps(2, salt="s"), salt="s")
    assert app._unsigners["s"] is unsigners
    assert len(unsigners) == 2


def test_new_secret_keys_forget_the_derived_ones():
    app = make_app(KEY_OLD)
    app.loads(app.dumps(1, salt="s"), salt="s")
    app.config.SECRET_KEYS = [KEY_NEW]
    app._setup_serializers()
    assert app._unsigners == {}
    assert app.loads(make_app(KEY_OLD).dumps(1, salt="s"), salt="s") is None


NOW = int(time.time())

UNSURE = {
    "another key": lambda: make_app(KEY_OLD).dumps({"id": 1}, salt="s"),
    "another salt": lambda: make_app(KEY_NEW).dumps({"id": 1}, salt="t"),
    "tampered payload": lambda: "x" + make_app(KEY_NEW).dumps({"id": 1}, salt="s")[1:],
    "tampered signature": lambda: make_app(KEY_NEW).dumps({"id": 1}, salt="s")[:-2] + "AA",
    "no dot": lambda: "garbage",
    "one dot": lambda: "a.b",
    "empty": lambda: "",
    "not base64": lambda: "a.b.!!!",
    "expired": lambda: sign(KEY_NEW, b"eyJpZCI6MX0", NOW - 120),
    "from the future": lambda: sign(KEY_NEW, b"eyJpZCI6MX0", NOW + 120),
    "after year 9999": lambda: sign(KEY_NEW, b"eyJpZCI6MX0", 253402300800),
    "payload not base64": lambda: sign(KEY_NEW, b"!!!", NOW),
    "payload not json": lambda: sign(KEY_NEW, base64_encode(b"{nope"), NOW),
    "payload not zlib": lambda: sign(KEY_NEW, b"." + base64_encode(b"not zlib"), NOW),
}


@pytest.mark.parametrize("case", UNSURE)
def test_what_the_serializers_refuse_is_left_to_them(case):
    app = make_app(KEY_NEW)
    token = UNSURE[case]()
    assert app._quick_loads(token, 60, "s") is _UNSURE
    assert app.loads(token, salt="s", max_age=60) is None
    assert by_the_serializers(app, token, max_age=60, salt="s") is None


def test_without_max_age_an_old_token_is_read():
    app = make_app(KEY_NEW)
    token = sign(KEY_NEW, b"eyJpZCI6MX0", NOW - 10**6)
    assert app._quick_loads(token, None, "s") == {"id": 1}
    assert by_the_serializers(app, token, salt="s") == {"id": 1}


def test_bytes_are_read_as_text():
    app = make_app(KEY_NEW)
    token = app.dumps({"id": 1}, salt="s").encode()
    assert app._quick_loads(token, None, "s") == {"id": 1}


def test_return_timestamp_goes_to_the_serializers():
    app = make_app(KEY_NEW)
    value, signed_at = app.loads(app.dumps({"id": 1}, salt="s"), salt="s", return_timestamp=True)
    assert value == {"id": 1}
    assert abs(signed_at.timestamp() - time.time()) < 5
