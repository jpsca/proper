from datetime import datetime, timezone

import pytest

from proper import Response
from proper import status as pstatus
from proper.core.response.headers import ResponseHeadersDict, enc_name
from proper.errors import InvalidHeader
from proper.helpers.asgi import make_test_scope


def _make_response(*, status=pstatus.ok, **scope_kw):
    """Build a Response with a valid ASGI scope."""
    scope = make_test_scope(**scope_kw)
    response = Response(scope, status=status)
    return response


def test_setitem_getitem():
    d = ResponseHeadersDict()
    d["Content-Type"] = "text/html"
    assert d.get("Content-Type") == "text/html"
    # __getitem__ returns the Header namedtuple
    h = d["Content-Type"]
    assert h.value == "text/html"
    assert h.name == "Content-Type"


def test_contains():
    d = ResponseHeadersDict()
    d["Content-Type"] = "text/html"
    assert "Content-Type" in d
    assert "content_type" in d


def test_set_none_deletes():
    d = ResponseHeadersDict()
    d["X-Custom"] = "value"
    assert "X-Custom" in d
    d["X-Custom"] = None
    assert "X-Custom" not in d


def test_get_default():
    d = ResponseHeadersDict()
    assert d.get("Missing") is None
    assert d.get("Missing", "default") == "default"


def test_setdefault_existing():
    d = ResponseHeadersDict()
    d["X-Custom"] = "original"
    d.setdefault("X-Custom", "new")
    assert d.get("X-Custom") == "original"


def test_setdefault_missing():
    d = ResponseHeadersDict()
    d.setdefault("X-Custom", "new")
    assert d.get("X-Custom") == "new"


def test_update():
    d = ResponseHeadersDict()
    d.update({"X-One": "1", "X-Two": "2"})
    assert d.get("X-One") == "1"
    assert d.get("X-Two") == "2"


def test_non_ascii_raises():
    with pytest.raises(InvalidHeader):
        enc_name("H\u00e9ader")


def test_delete_nonexistent():
    d = ResponseHeadersDict()
    d._set("X-Custom", None)  # should not raise


def test_default_content_type():
    resp = _make_response()
    assert resp.content_type == "text/html; charset=utf-8"


def test_mimetype_property():
    resp = _make_response()
    assert resp.mimetype == "text/html"


def test_mimetype_setter():
    resp = _make_response()
    resp.mimetype = "application/json"
    assert resp.mimetype == "application/json"


def test_charset_property():
    resp = _make_response()
    assert resp.charset == "utf-8"


def test_charset_setter():
    resp = _make_response()
    resp.charset = "iso-8859-1"
    assert resp.charset == "iso-8859-1"


def test_content_type_setter():
    resp = _make_response()
    resp.content_type = "application/json"
    assert resp.content_type == "application/json; charset=utf-8"


def test_accept_ranges():
    resp = _make_response()
    resp.accept_ranges = "bytes"
    assert resp.accept_ranges == "bytes"


def test_accept_ranges_none():
    resp = _make_response()
    resp.set_accept_ranges("bytes")
    resp.set_accept_ranges(None)
    assert resp.accept_ranges is None


def test_cache_control():
    resp = _make_response()
    resp.set_cache_control("no-cache", "no-store")
    assert resp.cache_control == ["no-cache", "no-store"]


def test_cache_control_setter_with_values():
    resp = _make_response()
    resp.cache_control = ["max-age=0", "private"]
    assert resp.cache_control == ["max-age=0", "private"]


def test_cache_control_setter_none():
    resp = _make_response()
    resp.set_cache_control("no-cache")
    resp.cache_control = None
    assert resp.cache_control is None


def test_cache_control_setter_empty():
    resp = _make_response()
    resp.set_cache_control("no-cache")
    resp.cache_control = []
    assert resp.cache_control is None


def test_content_encoding():
    resp = _make_response()
    resp.set_content_encoding("gzip")
    assert resp.content_encoding == ["gzip"]


def test_content_encoding_setter():
    resp = _make_response()
    resp.content_encoding = ["gzip", "deflate"]
    assert resp.content_encoding == ["gzip", "deflate"]


def test_content_encoding_setter_none():
    resp = _make_response()
    resp.set_content_encoding("gzip")
    resp.content_encoding = None
    assert resp.content_encoding is None


def test_content_encoding_setter_empty():
    resp = _make_response()
    resp.set_content_encoding("gzip")
    resp.content_encoding = []
    assert resp.content_encoding is None


def test_content_encoding_clear():
    resp = _make_response()
    resp.set_content_encoding("gzip")
    resp.set_content_encoding()
    assert resp.content_encoding is None


def test_content_length():
    resp = _make_response()
    resp.set_content_length(42)
    assert resp.content_length == 42


def test_content_length_setter():
    resp = _make_response()
    resp.content_length = 100
    assert resp.content_length == 100


def test_content_length_none():
    resp = _make_response()
    resp.set_content_length(42)
    resp.set_content_length(None)
    assert resp.content_length is None


def test_content_location():
    resp = _make_response()
    resp.set_content_location("/resource")
    assert resp.content_location == "/resource"


def test_content_location_setter():
    resp = _make_response()
    resp.content_location = "/other"
    assert resp.content_location == "/other"


def test_content_location_none():
    resp = _make_response()
    resp.set_content_location("/res")
    resp.set_content_location(None)
    assert resp.content_location is None


def test_content_range_full():
    resp = _make_response()
    resp.set_content_range("bytes", start=0, end=499, size=1000)
    assert resp.content_range == "bytes 0-499/1000"


def test_content_range_no_size():
    resp = _make_response()
    resp.set_content_range("bytes", start=0, end=499)
    assert resp.content_range == "bytes 0-499/*"


def test_content_range_no_range():
    resp = _make_response()
    resp.set_content_range("bytes", size=1000)
    assert resp.content_range == "bytes */1000"


def test_content_range_none():
    resp = _make_response()
    resp.set_content_range(None)
    assert resp.content_range is None


def test_etag():
    resp = _make_response()
    resp.set_etag(123)
    assert resp.etag is not None
    assert "W/" in resp.etag


def test_etag_strong():
    resp = _make_response()
    resp.set_etag("abc", strong=True)
    assert resp.etag and resp.etag.startswith('"')
    assert not resp.etag.startswith("W/")


def test_etag_none():
    resp = _make_response()
    resp.set_etag(123)
    resp.set_etag(None)
    assert resp.etag is None


def test_expires():
    resp = _make_response()
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    resp.set_expires(dt)
    assert resp.expires == dt


def test_expires_setter():
    resp = _make_response()
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    resp.expires = dt
    assert resp.expires == dt


def test_expires_none():
    resp = _make_response()
    resp.set_expires(datetime(2025, 1, 1))
    resp.set_expires(None)
    assert resp.expires is None


def test_expires_from_timestamp():
    resp = _make_response()
    resp.set_expires(1704067200)
    assert isinstance(resp.expires, datetime)


def test_last_modified():
    resp = _make_response()
    resp.set_last_modified(datetime(2020, 1, 1))
    assert isinstance(resp.last_modified, datetime)


def test_last_modified_setter():
    resp = _make_response()
    dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
    resp.last_modified = dt
    assert resp.last_modified == dt


def test_last_modified_none():
    resp = _make_response()
    resp.set_last_modified(datetime(2020, 1, 1))
    resp.set_last_modified(None)
    assert resp.last_modified is None


def test_last_modified_from_timestamp():
    resp = _make_response()
    resp.set_last_modified(1704067200.0)
    assert isinstance(resp.last_modified, datetime)


def test_location():
    resp = _make_response()
    resp.set_location("/other")
    assert resp.location == "/other"


def test_location_setter():
    resp = _make_response()
    resp.location = "/here"
    assert resp.location == "/here"


def test_location_none():
    resp = _make_response()
    resp.set_location("/here")
    resp.set_location(None)
    assert resp.location is None


def test_retry_after():
    resp = _make_response()
    resp.set_retry_after(120)
    assert resp.retry_after == 120


def test_retry_after_setter():
    resp = _make_response()
    resp.retry_after = 60
    assert resp.retry_after == 60


def test_retry_after_none():
    resp = _make_response()
    resp.set_retry_after(120)
    resp.set_retry_after(None)
    assert resp.retry_after is None


def test_retry_after_zero():
    resp = _make_response()
    resp.set_retry_after(0)
    assert resp.retry_after is None


def test_retry_after_string():
    resp = _make_response()
    resp.set_retry_after("30")
    assert resp.retry_after == 30


def test_vary():
    resp = _make_response()
    resp.set_vary("Accept", "Accept-Encoding")
    assert resp.vary == ["Accept", "Accept-Encoding"]


def test_vary_setter():
    resp = _make_response()
    resp.vary = ["Accept"]
    assert resp.vary == ["Accept"]


def test_vary_setter_none():
    resp = _make_response()
    resp.set_vary("Accept")
    resp.vary = None
    assert resp.vary is None


def test_vary_setter_empty():
    resp = _make_response()
    resp.set_vary("Accept")
    resp.vary = []
    assert resp.vary is None


def test_vary_clear():
    resp = _make_response()
    resp.set_vary("Accept")
    resp.set_vary()
    assert resp.vary is None


def test_mimetype_empty_string():
    resp = _make_response()
    resp._mimetype = ""
    assert resp.mimetype == ""


def test_charset_empty_string():
    resp = _make_response()
    resp._charset = ""
    assert resp.charset == ""
