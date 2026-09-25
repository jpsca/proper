import io
from datetime import datetime, timezone
from unittest.mock import MagicMock

from proper import DotDict, Response
from proper import status as pstatus
from proper.constants import FLASHES_SESSION_KEY
from proper.core.response.file_wrapper import FileWrapper
from proper.core.response.flash_messages import FlashMessages
from proper.core.response.response import is_iterable


def _make_response(*, status=pstatus.ok, app=None):
    response = Response(app, status=status)
    return response


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



class TestResponse:
    def test_default_status(self):
        resp = _make_response()
        assert resp.status == 200
        assert resp.status_code == 200

    def test_custom_status(self):
        resp = _make_response(status=pstatus.not_found)
        assert resp.status_code == 404

    def test_repr(self):
        resp = _make_response()
        r = repr(resp)
        assert "200" in r

    def test_has_body_false(self):
        resp = _make_response()
        assert resp.has_body is False

    def test_has_body_true(self):
        resp = _make_response()
        resp.body = "hello"
        assert resp.has_body is True

    def test_session_default(self):
        resp = _make_response()
        assert isinstance(resp.session, DotDict)

    def test_session_setter(self):
        resp = _make_response()
        resp.session = {"key": "val"}
        assert isinstance(resp.session, DotDict)
        assert resp.session["key"] == "val"

    def test_session_setter_from_dotdict(self):
        resp = _make_response()
        resp.session = DotDict({"a": 1})
        assert resp.session["a"] == 1

    def test_app_given(self):
        mock_app = MagicMock()
        resp = Response(mock_app)
        assert resp.app is mock_app


class TestPrepare:
    def test_string_body(self):
        resp = _make_response()
        resp.body = "Hello World"
        status, headers, body = resp.prepare()
        assert status == 200
        assert body == b"Hello World"

    def test_bytes_body(self):
        resp = _make_response()
        resp.body = b"binary"
        status, headers, body = resp.prepare()
        assert body == b"binary"

    def test_empty_body(self):
        resp = _make_response()
        status, headers, body = resp.prepare()
        assert body == b""

    def test_iterable_body(self):
        resp = _make_response()
        resp.body = [b"chunk1", b"chunk2"]
        resp.set_content_length(12)
        status, headers, body = resp.prepare()
        # Iterables are passed through for streaming, not joined
        assert b"".join(bytes(b) for b in body) == b"chunk1chunk2"

    def test_content_length_auto_set_from_str(self):
        resp = _make_response()
        resp.body = "hello"
        resp.prepare()
        assert resp.content_length == 5

    def test_content_length_auto_set_from_bytes(self):
        resp = _make_response()
        resp.body = b"12345"
        resp.prepare()
        assert resp.content_length == 5

    def test_content_length_not_overwritten(self):
        resp = _make_response()
        resp.body = b"hello"
        resp.set_content_length(99)
        resp.prepare()
        assert resp.content_length == 99

    def test_headers_are_strings(self):
        resp = _make_response()
        resp.body = b""
        status, headers, body = resp.prepare()
        assert headers
        for name, value in headers:
            assert isinstance(name, str)
            assert isinstance(value, str)

    def test_head_request_has_no_body(self):
        from proper.test_client import make_test_request

        resp = _make_response()
        resp.body = b"hidden"
        _, _, body = resp.prepare(make_test_request("/", method="HEAD"))
        assert body == b""

    def test_status_returned(self):
        resp = _make_response(status=pstatus.not_found)
        status, _, _ = resp.prepare()
        assert status == 404

    def test_file_wrapper_iterable_body(self):
        f = io.BytesIO(b"file content")
        resp = _make_response()
        resp.body = FileWrapper(f, block_size=4)
        resp.set_content_length(12)
        status, headers, body = resp.prepare()
        # FileWrapper is passed through for streaming
        assert b"".join(bytes(b) for b in body) == b"file content"


class TestRedirectTo:
    def test_redirect_to_url(self):
        resp = _make_response()
        resp.redirect_to("/login")
        assert resp.status == pstatus.see_other
        assert resp.location == "/login"
        assert "/login" in str(resp.body)

    def test_redirect_to_absolute_url(self):
        resp = _make_response()
        resp.redirect_to("http://example.com/other")
        assert resp.location == "http://example.com/other"

    def test_redirect_with_flash(self):
        resp = _make_response()
        resp.redirect_to("/home", flash="Welcome!", flash_cat="positive")
        assert resp.flash.flashes == [("positive", "Welcome!")]

    def test_redirect_custom_status(self):
        resp = _make_response()
        resp.redirect_to("/moved", status=pstatus.moved_permanently)
        assert resp.status == 301

    def test_redirect_to_route_name(self):
        mock_app = MagicMock()
        mock_app.url_for.return_value = "/users/42"
        resp = Response(mock_app)
        resp.redirect_to("users.show", obj=42, pk=42)
        mock_app.url_for.assert_called_once_with("users.show", object=42, pk=42)
        assert resp.location == "/users/42"


class TestGetHeaderTuples:
    def test_basic_headers(self):
        resp = _make_response()
        tuples = resp.get_header_tuples()
        names = [t[0] for t in tuples]
        assert "Content-Type" in names

    def test_204_excludes_content_headers(self):
        resp = _make_response(status=pstatus.no_content)
        resp.set_content_length(0)
        tuples = resp.get_header_tuples()
        names = [t[0].lower() for t in tuples]
        assert "content-type" not in names
        assert "content-length" not in names

    def test_304_excludes_content_headers(self):
        resp = _make_response(status=pstatus.not_modified)
        resp.set_content_length(0)
        resp.set_content_encoding("gzip")
        tuples = resp.get_header_tuples()
        names = [t[0].lower() for t in tuples]
        assert "content-type" not in names
        assert "content-encoding" not in names

    def test_datetime_header_formatted(self):
        resp = _make_response()
        resp.set_expires(datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        tuples = resp.get_header_tuples()
        exp_tuple = [t for t in tuples if t[0] == "Expires"]
        assert len(exp_tuple) == 1
        assert "GMT" in exp_tuple[0][1]

    def test_list_header_joined(self):
        resp = _make_response()
        resp.set_vary("Accept", "Accept-Encoding")
        tuples = resp.get_header_tuples()
        vary_tuple = [t for t in tuples if t[0] == "Vary"]
        assert len(vary_tuple) == 1
        assert "Accept, Accept-Encoding" in vary_tuple[0][1]

    def test_get_headers_list_includes_cookies(self):
        resp = _make_response()
        resp.set_cookie("foo", "bar")
        headers = resp.get_headers_list()
        cookie_headers = [h for h in headers if h[0] == "Set-Cookie"]
        assert len(cookie_headers) == 1

    def test_get_headers_list_multiple_cookies(self):
        resp = _make_response()
        resp.set_cookie("foo", "bar")
        resp.set_cookie("baz", "qux")
        headers = resp.get_headers_list()
        cookie_headers = [h for h in headers if h[0] == "Set-Cookie"]
        assert len(cookie_headers) == 2


class TestFlashMessages:
    def test_init_creates_key(self):
        resp = _make_response()
        assert FLASHES_SESSION_KEY in resp.session

    def test_message(self):
        resp = _make_response()
        resp.flash.message("info", "Hello!")
        assert resp.flash.flashes == [("info", "Hello!")]

    def test_multiple_messages(self):
        resp = _make_response()
        resp.flash.message("info", "First")
        resp.flash.message("error", "Second")
        assert len(resp.flash) == 2

    def test_iter(self):
        resp = _make_response()
        resp.flash.message("info", "Test")
        items = list(resp.flash)
        assert items == [("info", "Test")]

    def test_getitem(self):
        resp = _make_response()
        resp.flash.message("info", "Test")
        assert resp.flash[0] == ("info", "Test")

    def test_len(self):
        resp = _make_response()
        assert len(resp.flash) == 0
        resp.flash.message("info", "Test")
        assert len(resp.flash) == 1

    def test_flashes_setter(self):
        resp = _make_response()
        resp.flash.flashes = [("warn", "Warning")]
        assert resp.flash.flashes == [("warn", "Warning")]

    def test_flash_init_existing_key(self):
        resp = _make_response()
        resp.session[FLASHES_SESSION_KEY] = [("existing", "msg")]
        flash = FlashMessages(resp)
        assert flash.flashes == [("existing", "msg")]

