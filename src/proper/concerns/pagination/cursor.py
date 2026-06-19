"""Opaque cursor (de)serialization.

A cursor carries two things: the page *number* of the page it points to
(so geared sizing keeps working under cursor paging) and the ordered column
values of the last row already seen (the keyset).

Values are type-tagged so that `datetime`, `date`, `Decimal`, `UUID`
and friends survive the JSON round trip.

The whole thing is base64url-encoded; when a secret is configured it
is HMAC-SHA256 signed and verified on decode.
"""

import base64
import hashlib
import hmac
import json
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from ...errors import InvalidCursor


_UNSIGNED = b"0"
_SIGNED = b"1"
_SIG_LEN = 32  # sha256 digest size


def _encode_value(v):
    if v is None:
        return {"t": "null", "v": None}
    # bool checked before int because bool is a subclass of int.
    if isinstance(v, bool):
        return {"t": "bool", "v": v}
    if isinstance(v, int):
        return {"t": "int", "v": v}
    if isinstance(v, float):
        return {"t": "float", "v": v}
    if isinstance(v, str):
        return {"t": "str", "v": v}
    # datetime checked before date because datetime is a subclass of date.
    if isinstance(v, datetime):
        return {"t": "datetime", "v": v.isoformat()}
    if isinstance(v, date):
        return {"t": "date", "v": v.isoformat()}
    if isinstance(v, time):
        return {"t": "time", "v": v.isoformat()}
    if isinstance(v, Decimal):
        return {"t": "decimal", "v": str(v)}
    if isinstance(v, UUID):
        return {"t": "uuid", "v": str(v)}
    if isinstance(v, bytes):
        return {"t": "bytes", "v": base64.b64encode(v).decode("ascii")}
    raise InvalidCursor(f"unsupported value type for cursor: {type(v)!r}")


def _decode_value(d):
    try:
        t, v = d["t"], d["v"]
    except (TypeError, KeyError) as e:
        raise InvalidCursor("malformed cursor value") from e
    if t == "null":
        return None
    if t == "bool":
        return bool(v)
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    if t == "str":
        return v
    if t == "datetime":
        return datetime.fromisoformat(v)
    if t == "date":
        return date.fromisoformat(v)
    if t == "time":
        return time.fromisoformat(v)
    if t == "decimal":
        return Decimal(v)
    if t == "uuid":
        return UUID(v)
    if t == "bytes":
        return base64.b64decode(v)
    raise InvalidCursor(f"unknown cursor value tag: {t!r}")


def encode_cursor(number: int, values: list, secret: bytes | None = None) -> str:
    payload = json.dumps(
        {"n": number, "k": [_encode_value(v) for v in values]},
        separators=(",", ":"),
    ).encode("utf-8")
    if secret:
        sig = hmac.new(secret, payload, hashlib.sha256).digest()
        raw = _SIGNED + sig + payload
    else:
        raw = _UNSIGNED + payload
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: str, secret: bytes | None = None) -> tuple[int, list]:
    """Return `(page_number, values)` for a cursor token.

    Raises `InvalidCursor` on any tampering, signature mismatch, or
    structural problem.
    """
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except Exception as e:
        raise InvalidCursor("cursor is not valid base64url") from e
    if not raw:
        raise InvalidCursor("empty cursor")

    version, body = raw[:1], raw[1:]
    if version == _SIGNED:
        if secret is None:
            raise InvalidCursor("signed cursor received but no secret configured")
        sig, payload = body[:_SIG_LEN], body[_SIG_LEN:]
        expected = hmac.new(secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise InvalidCursor("cursor signature mismatch")
    elif version == _UNSIGNED:
        if secret is not None:
            raise InvalidCursor("unsigned cursor received but a secret is configured")
        payload = body
    else:
        raise InvalidCursor("unknown cursor version")

    try:
        data = json.loads(payload)
        number = int(data["n"])
        values = [_decode_value(d) for d in data["k"]]
    except InvalidCursor:
        raise
    except Exception as e:
        raise InvalidCursor("malformed cursor payload") from e
    if number < 1:
        raise InvalidCursor("cursor page number must be >= 1")
    return number, values
