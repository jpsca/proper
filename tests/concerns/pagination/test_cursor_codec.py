import base64
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest

from proper.concerns.pagination.cursor import decode_cursor, encode_cursor
from proper.errors import InvalidCursor


def _token(payload: bytes, version: bytes = b"0") -> str:
    """Build a raw cursor token from a hand-crafted payload (no signature)."""
    return base64.urlsafe_b64encode(version + payload).decode("ascii").rstrip("=")


def test_round_trip_mixed_types():
    values = [
        42,
        "hello",
        3.5,
        True,
        None,
        datetime(2020, 1, 2, 3, 4, 5),
        date(2021, 6, 1),
        time(12, 30),
        Decimal("10.25"),
        uuid4(),
        b"\x00\x01\x02",
    ]
    token = encode_cursor(7, values)
    number, decoded = decode_cursor(token)
    assert number == 7
    assert decoded == values


def test_bool_stays_bool_not_int():
    _, decoded = decode_cursor(encode_cursor(1, [True, 1]))
    assert decoded[0] is True
    assert isinstance(decoded[1], int) and decoded[1] is not True


def test_signed_round_trip_and_tamper_detection():
    secret = b"s3cret"
    token = encode_cursor(2, [1, 2], secret=secret)
    assert decode_cursor(token, secret=secret) == (2, [1, 2])

    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    with pytest.raises(InvalidCursor):
        decode_cursor(tampered, secret=secret)


def test_secret_mismatch_rules():
    token_signed = encode_cursor(1, [1], secret=b"k")
    with pytest.raises(InvalidCursor):
        decode_cursor(token_signed, secret=None)  # signed, no secret

    token_plain = encode_cursor(1, [1])
    with pytest.raises(InvalidCursor):
        decode_cursor(token_plain, secret=b"k")  # unsigned, secret set


def test_garbage_token():
    with pytest.raises(InvalidCursor):
        decode_cursor("!!!not-base64!!!")


def test_encode_rejects_an_unsupported_value_type():
    with pytest.raises(InvalidCursor):
        encode_cursor(1, [object()])


def test_decode_rejects_a_non_base64_token():
    with pytest.raises(InvalidCursor):
        decode_cursor("x")


def test_decode_rejects_an_empty_token():
    with pytest.raises(InvalidCursor):
        decode_cursor("")


def test_decode_rejects_a_malformed_payload():
    with pytest.raises(InvalidCursor):
        decode_cursor(_token(b"not json"))


def test_decode_rejects_a_malformed_value():
    # `k` should hold {"t", "v"} dicts, not bare scalars.
    with pytest.raises(InvalidCursor):
        decode_cursor(_token(b'{"n":1,"k":[42]}'))


def test_decode_rejects_an_unknown_value_tag():
    with pytest.raises(InvalidCursor):
        decode_cursor(_token(b'{"n":1,"k":[{"t":"zzz","v":1}]}'))


def test_decode_rejects_a_page_number_below_one():
    with pytest.raises(InvalidCursor):
        decode_cursor(encode_cursor(0, []))
