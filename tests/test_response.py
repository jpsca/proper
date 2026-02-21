"""Tests for proper.response — Response, headers, cookies, flash messages,
and file wrapper."""

import io
import warnings
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proper import DotDict, Request, Response
from proper.constants import FLASHES_SESSION_KEY
from proper.errors import InvalidHeader
from proper.response.cookies import (
    HOST_PREFIX,
    SECURE_PREFIX,
    validate_cookie_size,
    validate_domain,
)
from proper.response.file_wrapper import FileWrapper
from proper.response.flash_messages import FlashMessages
from proper.response.headers import (
    ResponseHeadersDict,
    enc_name,
    format_comma_list,
    format_datetime,
    format_header,
    format_int,
)
from proper.response.response import is_iterable


# ── is_iterable ──────────────────────────────────────────────────────


class TestIsIterable:
    def test_list(self):
        assert is_iterable([1, 2]) is True

    def test_tuple(self):
        assert is_iterable((1, 2)) is True

    def test_string_not_iterable(self):
        assert is_iterable("hello") is False

    def test_dict_not_iterable(self):
        assert is_iterable({"a": 1}) is False

    def test_bytes_is_iterable(self):
        assert is_iterable(b"hello") is True

    def test_none_not_iterable(self):
        assert is_iterable(None) is False

    def test_int_not_iterable(self):
        assert is_iterable(42) is False


# ── Response basics ──────────────────────────────────────────────────


class TestResponse:
    def test_default_status(self):
        resp = Response()
        assert resp.status == "200 OK"
        assert resp.status_code == 200

    def test_custom_status(self):
        resp = Response(status="404 Not Found")
        assert resp.status_code == 404

    def test_repr(self):
        resp = Response()
        r = repr(resp)
        assert "200 OK" in r

    def test_has_body_false(self):
        resp = Response()
        assert resp.has_body is False

    def test_has_body_true(self):
        resp = Response()
        resp.body = "hello"
        assert resp.has_body is True

    def test_session_default(self):
        resp = Response()
        assert isinstance(resp.session, DotDict)

    def test_session_setter(self):
        resp = Response()
        resp.session = {"key": "val"}
        assert isinstance(resp.session, DotDict)
        assert resp.session["key"] == "val"

    def test_session_setter_from_dotdict(self):
        resp = Response()
        resp.session = DotDict({"a": 1})
        assert resp.session["a"] == 1


class TestResponseCall:
    def test_call_with_string_body(self):
        resp = Response()
        resp.body = "Hello World"
        called = {}

        def start_response(status, headers):
            called["status"] = status
            called["headers"] = headers

        body = resp(start_response)
        assert called["status"] is not None
        assert isinstance(body, list)
        assert body[0] == b"Hello World"

    def test_call_with_bytes_body(self):
        resp = Response()
        resp.body = b"binary"

        def start_response(status, headers):
            pass

        body = resp(start_response)
        assert body == [b"binary"]

    def test_call_with_empty_body(self):
        resp = Response()

        def start_response(status, headers):
            pass

        body = resp(start_response)
        assert body == [b""]

    def test_call_with_iterable_body(self):
        resp = Response()
        resp.body = [b"chunk1", b"chunk2"]
        resp.set_content_length(12)

        def start_response(status, headers):
            pass

        body = resp(start_response)
        assert list(body) == [b"chunk1", b"chunk2"]


class TestPrepareBody:
    def test_string_body_encoded(self):
        resp = Response()
        resp.body = "hello"
        body = resp.prepare_body()
        assert body == [b"hello"]

    def test_bytes_body_wrapped(self):
        resp = Response()
        resp.body = b"data"
        body = resp.prepare_body()
        assert body == [b"data"]

    def test_content_length_auto_set(self):
        resp = Response()
        resp.body = b"12345"
        resp.prepare_body()
        assert resp.content_length == 5

    def test_iterable_body_passed_through(self):
        resp = Response()
        chunks = [b"a", b"b"]
        resp.body = chunks
        resp.set_content_length(2)
        body = resp.prepare_body()
        assert body is chunks

    def test_falsy_body_becomes_empty(self):
        resp = Response()
        resp.body = b""
        body = resp.prepare_body()
        assert body == [b""]

    def test_bytes_with_content_length_already_set(self):
        resp = Response()
        resp.body = b"hello"
        resp.set_content_length(5)
        body = resp.prepare_body()
        assert body == [b"hello"]


# ── redirect_to ──────────────────────────────────────────────────────


class TestRedirectTo:
    def test_redirect_to_url(self):
        resp = Response()
        resp.redirect_to("/login")
        assert resp.status == "303 See Other"
        assert resp.location == "/login"
        assert "/login" in resp.body

    def test_redirect_to_absolute_url(self):
        resp = Response()
        resp.redirect_to("http://example.com/other")
        assert resp.location == "http://example.com/other"

    def test_redirect_with_flash(self):
        resp = Response()
        resp.redirect_to("/home", flash="Welcome!", flash_type="success")
        assert resp.flash.flashes == [("success", "Welcome!")]

    def test_redirect_custom_status(self):
        resp = Response()
        resp.redirect_to("/moved", status="301 Moved Permanently")
        assert resp.status == "301 Moved Permanently"

    def test_redirect_to_route_name(self):
        app = MagicMock()
        app.url_for.return_value = "/users/42"
        resp = Response(app=app)
        resp.redirect_to("users.show", obj=42, pk=42)
        app.url_for.assert_called_once_with("users.show", object=42, pk=42)
        assert resp.location == "/users/42"


# ── fresh_when / is_fresh ────────────────────────────────────────────


class TestFreshWhen:
    def test_set_etag_weak(self):
        resp = Response()
        resp.fresh_when(etag=123, public=False)
        assert resp.etag.startswith('W/"')
        assert resp.cache_control == ["max-age=0", "private", "must-revalidate"]

    def test_set_etag_strong_public(self):
        resp = Response()
        resp.fresh_when(etag=123, strong=True, public=True)
        assert resp.etag.startswith('"')
        assert not resp.etag.startswith("W/")
        assert resp.cache_control == ["max-age=0", "public", "must-revalidate"]

    def test_set_etag_from_datetime(self):
        resp = Response()
        resp.fresh_when(etag=datetime(2020, 11, 24, 17, 17, 0))
        assert resp.etag is not None

    def test_from_single_object(self):
        resp = Response()
        obj = DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)})
        resp.fresh_when(obj)
        assert resp.etag is not None
        assert resp.last_modified == datetime(2020, 11, 24, 17, 17, 0, tzinfo=timezone.utc)

    def test_from_list_of_objects(self):
        resp = Response()
        resp.fresh_when([
            DotDict({"updated_at": datetime(2020, 5, 5)}),
            DotDict({"updated_at": datetime(2020, 11, 24, 17, 17, 0)}),
            DotDict({"updated_at": datetime(2020, 7, 28)}),
        ])
        assert resp.last_modified == datetime(2020, 11, 24, 17, 17, 0, tzinfo=timezone.utc)

    def test_from_objects_with_none_filtered(self):
        resp = Response()
        resp.fresh_when([
            None,
            DotDict({"updated_at": datetime(2020, 1, 1)}),
        ])
        assert resp.etag is not None

    def test_empty_iterable_no_etag(self):
        resp = Response()
        resp.fresh_when([])
        # Empty list means objects is falsy, etag/last_modified default to None
        assert resp.etag is None

    def test_all_none_objects(self):
        resp = Response()
        resp.fresh_when([None, None])
        # All None => dates is empty, so etag/last_modified stay as None
        assert resp.etag is None

    def test_invalid_etag_value(self):
        resp = Response()
        assert not resp.fresh_when({})
        assert resp.etag is None


class TestIsFresh:
    def test_no_request(self):
        resp = Response()
        assert resp.is_fresh(request=None) is False

    def test_etag_match(self):
        resp = Response()
        resp.fresh_when(etag=123)
        request = Request(HTTP_IF_NONE_MATCH=resp.etag)
        assert resp.is_fresh(request=request) is True

    def test_etag_no_match(self):
        resp = Response()
        resp.fresh_when(etag=123)
        request = Request(HTTP_IF_NONE_MATCH='W/"abc"')
        assert resp.is_fresh(request=request) is False

    def test_last_modified_fresh(self):
        resp = Response()
        resp.set_last_modified(datetime(2019, 1, 1))
        resp.set_etag(None)
        request = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2020 07:28:00 GMT")
        assert resp.is_fresh(request=request) is True

    def test_last_modified_stale(self):
        resp = Response()
        resp.set_last_modified(datetime(2020, 11, 24))
        resp.set_etag(None)
        request = Request(HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT")
        assert resp.is_fresh(request=request) is False

    def test_etag_takes_priority_over_last_modified(self):
        resp = Response()
        resp.fresh_when(etag=123)
        # ETag matches, even though Last-Modified would not
        request = Request(
            HTTP_IF_NONE_MATCH=resp.etag,
            HTTP_IF_MODIFIED_SINCE="Wed, 21 Oct 2015 07:28:00 GMT",
        )
        assert resp.is_fresh(request=request) is True

    def test_empty_if_none_match(self):
        resp = Response()
        resp.fresh_when(etag=123)
        request = Request(HTTP_IF_NONE_MATCH="")
        assert resp.is_fresh(request=request) is False


# ── send_file ────────────────────────────────────────────────────────


class TestSendFile:
    def test_send_file_basic(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello World")

        resp = Response()
        resp.send_file(f)
        assert "text/plain" in resp.content_type
        assert "hello.txt" in resp.headers.get("content-disposition")
        assert "inline" in resp.headers.get("content-disposition")
        assert resp.content_length == 11

    def test_send_file_as_attachment(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c")

        resp = Response()
        resp.send_file(f, as_attachment=True)
        assert "attachment" in resp.headers.get("content-disposition")

    def test_send_file_custom_mimetype(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01")

        resp = Response()
        resp.send_file(f, mimetype="application/octet-stream")
        assert resp.mimetype == "application/octet-stream"

    def test_send_file_custom_download_name(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00")

        resp = Response()
        resp.send_file(f, download_name="custom.bin")
        assert "custom.bin" in resp.headers.get("content-disposition")

    def test_send_file_unicode_download_name(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00")

        resp = Response()
        resp.send_file(f, download_name="resum\u00e9.pdf")
        disp = resp.headers.get("content-disposition")
        assert "filename*=UTF-8''" in disp

    def test_send_file_x_sendfile(self, tmp_path):
        subdir = tmp_path / "app"
        subdir.mkdir()
        f = tmp_path / "file.txt"
        f.write_text("content")

        app = MagicMock()
        app.root_path = subdir  # parent is tmp_path

        resp = Response(app=app)
        resp.send_file(f, x_sendfile_header="X-Accel-Redirect")
        assert resp.headers.get("X-Accel-Redirect") == "/file.txt"
        assert resp.body == ""

    def test_send_file_gzip_encoding_inline(self, tmp_path):
        f = tmp_path / "archive.tar.gz"
        f.write_bytes(b"\x00" * 10)

        resp = Response()
        resp.send_file(f)
        # gzip encoding should be set for non-attachment
        assert resp.content_encoding == ["gzip"]

    def test_send_file_gzip_encoding_attachment(self, tmp_path):
        f = tmp_path / "archive.tar.gz"
        f.write_bytes(b"\x00" * 10)

        resp = Response()
        resp.send_file(f, as_attachment=True)
        # encoding not set for attachments
        assert resp.content_encoding is None

    def test_send_file_unknown_mimetype(self, tmp_path):
        f = tmp_path / "file.unknownext"
        f.write_bytes(b"data")

        resp = Response()
        resp.send_file(f)
        assert resp.mimetype == "application/octet-stream"

    def test_send_file_skips_content_length_when_st_size_none(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello")

        fake_stat = MagicMock()
        fake_stat.st_size = None
        fake_stat.st_mtime = 1704067200.0

        resp = Response()
        with patch.object(Path, "stat", return_value=fake_stat):
            resp.send_file(f)
        assert resp.content_length is None

    def test_send_file_uses_wsgi_file_wrapper(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello")

        class CustomWrapper:
            def __init__(self, file, block_size):
                self.file = file

        resp = Response(**{"wsgi.file_wrapper": CustomWrapper})
        resp.send_file(f)
        assert isinstance(resp.body, CustomWrapper)

    def test_wrap_file_fallback(self):
        resp = Response()
        f = io.BytesIO(b"data")
        result = resp._wrap_file(f)
        assert isinstance(result, FileWrapper)


# ── ResponseHeadersDict ──────────────────────────────────────────────


class TestResponseHeadersDict:
    def test_setitem_getitem(self):
        d = ResponseHeadersDict()
        d["Content-Type"] = "text/html"
        assert d.get("Content-Type") == "text/html"
        # __getitem__ returns the Header namedtuple
        assert d["Content-Type"].value == "text/html"

    def test_contains(self):
        d = ResponseHeadersDict()
        d["Content-Type"] = "text/html"
        assert "Content-Type" in d
        assert "content_type" in d

    def test_set_none_deletes(self):
        d = ResponseHeadersDict()
        d["X-Custom"] = "value"
        assert "X-Custom" in d
        d["X-Custom"] = None
        assert "X-Custom" not in d

    def test_get_default(self):
        d = ResponseHeadersDict()
        assert d.get("Missing") is None
        assert d.get("Missing", "default") == "default"

    def test_setdefault_existing(self):
        d = ResponseHeadersDict()
        d["X-Custom"] = "original"
        d.setdefault("X-Custom", "new")
        assert d.get("X-Custom") == "original"

    def test_setdefault_missing(self):
        d = ResponseHeadersDict()
        d.setdefault("X-Custom", "new")
        assert d.get("X-Custom") == "new"

    def test_update(self):
        d = ResponseHeadersDict()
        d.update({"X-One": "1", "X-Two": "2"})
        assert d.get("X-One") == "1"
        assert d.get("X-Two") == "2"

    def test_non_ascii_raises(self):
        with pytest.raises(InvalidHeader):
            enc_name("Héader")


# ── ResponseHeadersMixin ─────────────────────────────────────────────


class TestResponseHeadersMixin:
    def test_default_content_type(self):
        resp = Response()
        assert resp.content_type == "text/html; charset=utf-8"

    def test_mimetype_property(self):
        resp = Response()
        assert resp.mimetype == "text/html"

    def test_mimetype_setter(self):
        resp = Response()
        resp.mimetype = "application/json"
        assert resp.mimetype == "application/json"

    def test_charset_property(self):
        resp = Response()
        assert resp.charset == "utf-8"

    def test_charset_setter(self):
        resp = Response()
        resp.charset = "iso-8859-1"
        assert resp.charset == "iso-8859-1"

    def test_content_type_setter(self):
        resp = Response()
        resp.content_type = "application/json"
        assert resp.content_type == "application/json; charset=utf-8"

    def test_accept_ranges(self):
        resp = Response()
        resp.accept_ranges = "bytes"
        assert resp.accept_ranges == "bytes"

    def test_accept_ranges_none(self):
        resp = Response()
        resp.set_accept_ranges("bytes")
        resp.set_accept_ranges(None)
        assert resp.accept_ranges is None

    def test_cache_control(self):
        resp = Response()
        resp.set_cache_control("no-cache", "no-store")
        assert resp.cache_control == ["no-cache", "no-store"]

    def test_cache_control_setter_with_values(self):
        resp = Response()
        resp.cache_control = ["max-age=0", "private"]
        assert resp.cache_control == ["max-age=0", "private"]

    def test_cache_control_setter_none(self):
        resp = Response()
        resp.set_cache_control("no-cache")
        resp.cache_control = None
        assert resp.cache_control is None

    def test_cache_control_setter_empty(self):
        resp = Response()
        resp.set_cache_control("no-cache")
        resp.cache_control = []
        assert resp.cache_control is None

    def test_content_encoding(self):
        resp = Response()
        resp.set_content_encoding("gzip")
        assert resp.content_encoding == ["gzip"]

    def test_content_encoding_setter(self):
        resp = Response()
        resp.content_encoding = ["gzip", "deflate"]
        assert resp.content_encoding == ["gzip", "deflate"]

    def test_content_encoding_setter_none(self):
        resp = Response()
        resp.set_content_encoding("gzip")
        resp.content_encoding = None
        assert resp.content_encoding is None

    def test_content_encoding_setter_empty(self):
        resp = Response()
        resp.set_content_encoding("gzip")
        resp.content_encoding = []
        assert resp.content_encoding is None

    def test_content_encoding_clear(self):
        resp = Response()
        resp.set_content_encoding("gzip")
        resp.set_content_encoding()
        assert resp.content_encoding is None

    def test_content_length(self):
        resp = Response()
        resp.set_content_length(42)
        assert resp.content_length == 42

    def test_content_length_setter(self):
        resp = Response()
        resp.content_length = 100
        assert resp.content_length == 100

    def test_content_length_none(self):
        resp = Response()
        resp.set_content_length(42)
        resp.set_content_length(None)
        assert resp.content_length is None

    def test_content_location(self):
        resp = Response()
        resp.set_content_location("/resource")
        assert resp.content_location == "/resource"

    def test_content_location_setter(self):
        resp = Response()
        resp.content_location = "/other"
        assert resp.content_location == "/other"

    def test_content_location_none(self):
        resp = Response()
        resp.set_content_location("/res")
        resp.set_content_location(None)
        assert resp.content_location is None

    def test_content_range_full(self):
        resp = Response()
        resp.set_content_range("bytes", start=0, end=499, size=1000)
        assert resp.content_range == "bytes 0-499/1000"

    def test_content_range_no_size(self):
        resp = Response()
        resp.set_content_range("bytes", start=0, end=499)
        assert resp.content_range == "bytes 0-499/*"

    def test_content_range_no_range(self):
        resp = Response()
        resp.set_content_range("bytes", size=1000)
        assert resp.content_range == "bytes */1000"

    def test_content_range_none(self):
        resp = Response()
        resp.set_content_range(None)
        assert resp.content_range is None

    def test_etag(self):
        resp = Response()
        resp.set_etag(123)
        assert resp.etag is not None
        assert "W/" in resp.etag

    def test_etag_strong(self):
        resp = Response()
        resp.set_etag("abc", strong=True)
        assert resp.etag.startswith('"')
        assert not resp.etag.startswith("W/")

    def test_etag_none(self):
        resp = Response()
        resp.set_etag(123)
        resp.set_etag(None)
        assert resp.etag is None

    def test_expires(self):
        resp = Response()
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        resp.set_expires(dt)
        assert resp.expires == dt

    def test_expires_setter(self):
        resp = Response()
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        resp.expires = dt
        assert resp.expires == dt

    def test_expires_none(self):
        resp = Response()
        resp.set_expires(datetime(2025, 1, 1))
        resp.set_expires(None)
        assert resp.expires is None

    def test_expires_from_timestamp(self):
        resp = Response()
        resp.set_expires(1704067200)
        assert isinstance(resp.expires, datetime)

    def test_last_modified(self):
        resp = Response()
        resp.set_last_modified(datetime(2020, 1, 1))
        assert isinstance(resp.last_modified, datetime)

    def test_last_modified_setter(self):
        resp = Response()
        dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        resp.last_modified = dt
        assert resp.last_modified == dt

    def test_last_modified_none(self):
        resp = Response()
        resp.set_last_modified(datetime(2020, 1, 1))
        resp.set_last_modified(None)
        assert resp.last_modified is None

    def test_last_modified_from_timestamp(self):
        resp = Response()
        resp.set_last_modified(1704067200.0)
        assert isinstance(resp.last_modified, datetime)

    def test_location(self):
        resp = Response()
        resp.set_location("/other")
        assert resp.location == "/other"

    def test_location_setter(self):
        resp = Response()
        resp.location = "/here"
        assert resp.location == "/here"

    def test_location_none(self):
        resp = Response()
        resp.set_location("/here")
        resp.set_location(None)
        assert resp.location is None

    def test_retry_after(self):
        resp = Response()
        resp.set_retry_after(120)
        assert resp.retry_after == 120

    def test_retry_after_setter(self):
        resp = Response()
        resp.retry_after = 60
        assert resp.retry_after == 60

    def test_retry_after_none(self):
        resp = Response()
        resp.set_retry_after(120)
        resp.set_retry_after(None)
        assert resp.retry_after is None

    def test_retry_after_zero(self):
        resp = Response()
        resp.set_retry_after(0)
        assert resp.retry_after is None

    def test_retry_after_string(self):
        resp = Response()
        resp.set_retry_after("30")
        assert resp.retry_after == 30

    def test_vary(self):
        resp = Response()
        resp.set_vary("Accept", "Accept-Encoding")
        assert resp.vary == ["Accept", "Accept-Encoding"]

    def test_vary_setter(self):
        resp = Response()
        resp.vary = ["Accept"]
        assert resp.vary == ["Accept"]

    def test_vary_setter_none(self):
        resp = Response()
        resp.set_vary("Accept")
        resp.vary = None
        assert resp.vary is None

    def test_vary_setter_empty(self):
        resp = Response()
        resp.set_vary("Accept")
        resp.vary = []
        assert resp.vary is None

    def test_vary_clear(self):
        resp = Response()
        resp.set_vary("Accept")
        resp.set_vary()
        assert resp.vary is None


# ── get_header_tuples / get_headers_list ─────────────────────────────


class TestGetHeaderTuples:
    def test_basic_headers(self):
        resp = Response()
        tuples = resp.get_header_tuples()
        names = [t[0] for t in tuples]
        assert "Content-Type" in names

    def test_204_excludes_content_headers(self):
        resp = Response(status="204 No Content")
        resp.set_content_length(0)
        tuples = resp.get_header_tuples()
        names = [t[0].lower() for t in tuples]
        assert "content-type" not in names
        assert "content-length" not in names

    def test_304_excludes_content_headers(self):
        resp = Response(status="304 Not Modified")
        resp.set_content_length(0)
        resp.set_content_encoding("gzip")
        tuples = resp.get_header_tuples()
        names = [t[0].lower() for t in tuples]
        assert "content-type" not in names
        assert "content-encoding" not in names

    def test_datetime_header_formatted(self):
        resp = Response()
        resp.set_expires(datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        tuples = resp.get_header_tuples()
        exp_tuple = [t for t in tuples if t[0] == "Expires"]
        assert len(exp_tuple) == 1
        assert "GMT" in exp_tuple[0][1]

    def test_list_header_joined(self):
        resp = Response()
        resp.set_vary("Accept", "Accept-Encoding")
        tuples = resp.get_header_tuples()
        vary_tuple = [t for t in tuples if t[0] == "Vary"]
        assert len(vary_tuple) == 1
        assert "Accept, Accept-Encoding" in vary_tuple[0][1]

    def test_get_headers_list_includes_cookies(self):
        resp = Response()
        resp.set_cookie("foo", "bar")
        headers = resp.get_headers_list()
        cookie_headers = [h for h in headers if h[0] == "Set-Cookie"]
        assert len(cookie_headers) == 1


# ── Cookies ──────────────────────────────────────────────────────────


class TestCookies:
    def test_no_cookies(self):
        resp = Response()
        assert not resp.cookies

    def test_set_minimal_cookie(self):
        resp = Response()
        resp.set_cookie("foo", "bar")
        assert resp.cookies["foo"].value == "bar"
        assert resp.cookies["foo"]["path"] == "/"
        assert resp.cookies["foo"]["samesite"] == "Lax"

    def test_cookie_tuples_single(self):
        resp = Response()
        resp.set_cookie("foo", "bar")
        tuples = resp._get_cookie_tuples()
        assert len(tuples) == 1
        assert tuples[0][0] == "Set-Cookie"
        assert "foo=bar" in tuples[0][1]

    def test_invalid_samesite(self):
        resp = Response()
        with pytest.raises(ValueError):
            resp.set_cookie("foo", "bar", samesite="invalid")

    def test_cookie_no_path(self):
        resp = Response()
        resp.set_cookie("foo", "bar", path=None)
        headers = resp.get_headers_list()
        cookie_header = [h for h in headers if h[0] == "Set-Cookie"][0][1]
        assert "foo=bar" in cookie_header

    def test_cookie_max_age(self):
        resp = Response()
        resp.set_cookie("foo", "bar", max_age=3600)
        assert resp.cookies["foo"]["max-age"] == 3600
        assert resp.cookies["foo"]["expires"]

    def test_cookie_domain(self):
        resp = Response()
        resp.set_cookie("foo", "bar", domain="example.com")
        assert resp.cookies["foo"]["domain"] == "example.com"

    def test_cookie_secure(self):
        resp = Response()
        resp.set_cookie("foo", "bar", secure=True)
        assert resp.cookies["foo"]["secure"]

    def test_cookie_httponly(self):
        resp = Response()
        resp.set_cookie("foo", "bar", httponly=True)
        assert resp.cookies["foo"]["httponly"]

    def test_cookie_samesite_strict(self):
        resp = Response()
        resp.set_cookie("foo", "bar", samesite="Strict")
        assert resp.cookies["foo"]["samesite"] == "Strict"

    def test_cookie_samesite_none(self):
        resp = Response()
        resp.set_cookie("foo", "bar", samesite=None)
        assert resp.cookies["foo"]["samesite"] == ""

    def test_cookie_comment(self):
        resp = Response()
        resp.set_cookie("foo", "bar", comment="test comment")
        assert resp.cookies["foo"]["comment"] == "test comment"

    def test_cookie_integer_value(self):
        resp = Response()
        resp.set_cookie("count", 42)
        assert resp.cookies["count"].value == "42"

    def test_cookie_bytes_value(self):
        resp = Response()
        resp.set_cookie("data", b"hello")
        assert resp.cookies["data"].value == "hello"

    def test_filter_cookie_name(self):
        resp = Response()
        resp.set_cookie("fo,o=!", "bar")
        assert "foo!" in resp.cookies

    def test_host_prefix_forces_path(self):
        resp = Response()
        key = HOST_PREFIX + "mycookie"
        resp.set_cookie(key, "val", path="/admin")
        assert resp.cookies[key]["path"] == "/"

    def test_host_prefix_no_domain(self):
        resp = Response()
        key = HOST_PREFIX + "mycookie"
        resp.set_cookie(key, "val", domain="example.com")
        assert not resp.cookies[key]["domain"]

    def test_host_prefix_secure(self):
        resp = Response()
        key = HOST_PREFIX + "mycookie"
        resp.set_cookie(key, "val")
        assert resp.cookies[key]["secure"]

    def test_secure_prefix_secure(self):
        resp = Response()
        key = SECURE_PREFIX + "mycookie"
        resp.set_cookie(key, "val")
        assert resp.cookies[key]["secure"]

    def test_unset_cookie(self):
        resp = Response()
        resp.unset_cookie("foo")
        assert resp.cookies["foo"].value == " "
        assert resp.cookies["foo"]["max-age"] == 0

    def test_set_same_cookie_overwrites(self):
        resp = Response()
        resp.set_cookie("foo", "bar1")
        resp.set_cookie("foo", "bar2")
        assert len(resp.cookies) == 1
        assert resp.cookies["foo"].value == "bar2"

    def test_set_several_cookies(self):
        resp = Response()
        resp.set_cookie("foo", "bar")
        resp.set_cookie("baz", "qux")
        headers = resp.get_headers_list()
        cookie_headers = [h for h in headers if h[0] == "Set-Cookie"]
        assert len(cookie_headers) == 1
        assert "foo=bar" in cookie_headers[0][1]
        assert "baz=qux" in cookie_headers[0][1]

    def test_disable_cookies(self):
        resp = Response()
        resp.set_cookie("foo", "bar")
        resp.disable_cookies = True
        assert resp._get_cookie_tuples() == []

    def test_set_signed_cookie(self):
        import itsdangerous

        s = itsdangerous.URLSafeTimedSerializer("secret")
        app = MagicMock()
        app.get_serializer.return_value = s

        from proper.global_context import current
        current.app = app

        resp = Response()
        resp.set_signed_cookie("token", "hello")
        assert resp.cookies["token"].value != "hello"

        current.app = None

    def test_warn_for_big_cookie(self):
        resp = Response()
        with pytest.warns(UserWarning, match="too large"):
            resp.set_cookie("foo", "a" * 4093)

    def test_warn_for_localhost_domain(self):
        resp = Response()
        with pytest.warns(UserWarning, match="localhost"):
            resp.set_cookie("foo", "bar", domain="localhost")

    def test_max_cookie_size_zero_skips_validation(self):
        resp = Response()
        resp.max_cookie_size = 0
        # Should not warn even for a large cookie
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            resp.set_cookie("foo", "a" * 5000)


# ── validate_domain / validate_cookie_size ───────────────────────────


class TestValidateDomain:
    def test_valid_domain(self):
        # Should not warn
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            validate_domain("example.com")

    def test_none_domain(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            validate_domain(None)

    def test_localhost_warns(self):
        with pytest.warns(UserWarning, match="localhost"):
            validate_domain("localhost")


class TestValidateCookieSize:
    def test_within_limit(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            validate_cookie_size("foo", "short", 100)

    def test_exceeds_limit(self):
        with pytest.warns(UserWarning, match="too large"):
            validate_cookie_size("foo", "x" * 200, 100)

    def test_warning_contains_sizes(self):
        with pytest.warns(UserWarning, match="200 bytes") as record:
            validate_cookie_size("foo", "x" * 200, 100)
        assert "100 bytes" in str(record[0].message)


# ── FlashMessages ────────────────────────────────────────────────────


class TestFlashMessages:
    def test_init_creates_key(self):
        resp = Response()
        assert FLASHES_SESSION_KEY in resp.session

    def test_message(self):
        resp = Response()
        resp.flash.message("info", "Hello!")
        assert resp.flash.flashes == [("info", "Hello!")]

    def test_multiple_messages(self):
        resp = Response()
        resp.flash.message("info", "First")
        resp.flash.message("error", "Second")
        assert len(resp.flash) == 2

    def test_iter(self):
        resp = Response()
        resp.flash.message("info", "Test")
        items = list(resp.flash)
        assert items == [("info", "Test")]

    def test_getitem(self):
        resp = Response()
        resp.flash.message("info", "Test")
        assert resp.flash[0] == ("info", "Test")

    def test_len(self):
        resp = Response()
        assert len(resp.flash) == 0
        resp.flash.message("info", "Test")
        assert len(resp.flash) == 1

    def test_flashes_setter(self):
        resp = Response()
        resp.flash.flashes = [("warn", "Warning")]
        assert resp.flash.flashes == [("warn", "Warning")]

    def test_flash_init_existing_key(self):
        resp = Response()
        resp.session[FLASHES_SESSION_KEY] = [("existing", "msg")]
        flash = FlashMessages(resp)
        # Should not overwrite existing flashes
        assert flash.flashes == [("existing", "msg")]


# ── FileWrapper ──────────────────────────────────────────────────────


class TestFileWrapper:
    def test_iter(self):
        f = io.BytesIO(b"hello world")
        wrapper = FileWrapper(f, block_size=5)
        chunks = list(wrapper)
        assert b"".join(chunks) == b"hello world"

    def test_close(self):
        f = io.BytesIO(b"data")
        wrapper = FileWrapper(f)
        wrapper.close()
        assert f.closed

    def test_close_no_close_method(self):
        class NoClose:
            def read(self, n):
                return b""

        wrapper = FileWrapper(NoClose())
        wrapper.close()  # should not raise

    def test_seekable_true(self):
        f = io.BytesIO(b"data")
        wrapper = FileWrapper(f)
        assert wrapper.seekable() is True

    def test_seekable_false(self):
        class NoSeek:
            def read(self, n):
                return b""

        wrapper = FileWrapper(NoSeek())
        assert wrapper.seekable() is False

    def test_seekable_via_seek_method(self):
        class HasSeek:
            def read(self, n):
                return b""

            def seek(self, *args):
                pass

        wrapper = FileWrapper(HasSeek())
        assert wrapper.seekable() is True

    def test_seek(self):
        f = io.BytesIO(b"hello world")
        wrapper = FileWrapper(f)
        wrapper.seek(5)
        assert f.tell() == 5

    def test_seek_no_seek_method(self):
        class NoSeek:
            def read(self, n):
                return b""

        wrapper = FileWrapper(NoSeek())
        wrapper.seek(5)  # should not raise

    def test_tell(self):
        f = io.BytesIO(b"hello")
        wrapper = FileWrapper(f)
        assert wrapper.tell() == 0
        f.read(3)
        assert wrapper.tell() == 3

    def test_tell_no_tell_method(self):
        class NoTell:
            def read(self, n):
                return b""

        wrapper = FileWrapper(NoTell())
        assert wrapper.tell() is None

    def test_iter_returns_self(self):
        f = io.BytesIO(b"")
        wrapper = FileWrapper(f)
        assert iter(wrapper) is wrapper

    def test_empty_read_stops(self):
        f = io.BytesIO(b"")
        wrapper = FileWrapper(f)
        chunks = list(wrapper)
        assert chunks == []


# ── Formatter helpers ────────────────────────────────────────────────


class TestFormatters:
    def test_format_datetime_none(self):
        assert format_datetime(None) is None

    def test_format_datetime_from_float(self):
        result = format_datetime(1704067200.0)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_format_datetime_from_int(self):
        result = format_datetime(1704067200)
        assert isinstance(result, datetime)

    def test_format_datetime_naive(self):
        dt = datetime(2025, 1, 1)
        result = format_datetime(dt)
        assert result.tzinfo == timezone.utc

    def test_format_datetime_aware(self):
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = format_datetime(dt)
        assert result.tzinfo == timezone.utc

    def test_format_comma_list(self):
        result = format_comma_list("a", "b", "c")
        assert result == ["a", "b", "c"]

    def test_format_int_none(self):
        assert format_int(None) is None

    def test_format_int_zero(self):
        assert format_int(0) is None

    def test_format_int_from_string(self):
        assert format_int("42") == 42

    def test_format_int_value(self):
        assert format_int(42) == 42

    def test_format_header_none(self):
        assert format_header(None) is None

    def test_format_header_simple(self):
        assert format_header("text/html") == "text/html"

    def test_format_header_with_params(self):
        result = format_header("text/html", charset="utf-8")
        assert result == "text/html; charset=utf-8"

    def test_format_header_skips_falsy_params(self):
        result = format_header("text/html", charset="", encoding="gzip")
        assert result == "text/html; encoding=gzip"

    def test_enc_name_strips_and_normalizes(self):
        assert enc_name("  Content_Type  ") == "Content-Type"

    def test_enc_name_removes_http_prefix(self):
        assert enc_name("http-Content-Type") == "Content-Type"
        assert enc_name("HTTP-Content-Type") == "Content-Type"
