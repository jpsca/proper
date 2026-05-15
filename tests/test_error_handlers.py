"""Tests for proper.error_handlers — fallback/debug error pages & helpers."""

from unittest.mock import MagicMock, PropertyMock, patch

from proper.error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
    get_request_data,
    get_title,
    is_index,
    redact_sensitive_info,
    redact_value,
    render,
    render_default_index,
)


# ═══════════════════════════════════════════════════════════════════
# render
# ═══════════════════════════════════════════════════════════════════


class TestRender:
    def test_no_data_reads_raw_file(self):
        body = render("fallback-error.html")
        assert isinstance(body, str)
        assert len(body) > 0

    def test_with_data_uses_jinja(self):
        body = render(
            "default-index.jx",
            proper_version="1.0",
            server_software="test",
            python_version="3.14",
        )
        assert "1.0" in body

    def test_template_error_falls_back(self):
        with patch("proper.error_handlers.jinja_render", side_effect=Exception("boom")):
            body = render("debug-error.jx", some_data="x")
        # Should fall back to the static fallback-error.html
        assert isinstance(body, str)
        assert len(body) > 0


# ═══════════════════════════════════════════════════════════════════
# redact_sensitive_info / redact_value
# ═══════════════════════════════════════════════════════════════════


class TestRedactValue:
    def test_masks_after_four_chars(self):
        assert redact_value("abcdefgh") == "abcd▒▒▒▒"

    def test_short_value(self):
        assert redact_value("abcd") == "abcd"


class TestRedactSensibleInfo:
    def test_redacts_secret_keys(self):
        data = {"SECRET_KEYS": ["supersecretkey123"]}
        result = redact_sensitive_info(data)
        assert result["SECRET_KEYS"][0].startswith("supe")
        assert "▒" in result["SECRET_KEYS"][0]

    def test_redacts_password(self):
        data = {"password": "mysecretpass"}
        result = redact_sensitive_info(data)
        assert result["password"].startswith("myse")
        assert "▒" in result["password"]

    def test_leaves_non_sensitive_fields(self):
        data = {"DEBUG": True, "HOST": "localhost"}
        result = redact_sensitive_info(data)
        assert result["DEBUG"] is True
        assert result["HOST"] == "localhost"

    def test_recurses_into_nested_dicts(self):
        data = {"DATABASES": {"main": {"password": "dbpass123"}}}
        result = redact_sensitive_info(data)
        assert "▒" in result["DATABASES"]["main"]["password"]

    def test_no_secret_keys(self):
        data = {"DEBUG": False}
        result = redact_sensitive_info(data)
        assert result == {"DEBUG": False}

    def test_falsy_password_not_redacted(self):
        data = {"password": ""}
        result = redact_sensitive_info(data)
        assert result["password"] == ""


# ═══════════════════════════════════════════════════════════════════
# is_index
# ═══════════════════════════════════════════════════════════════════


class TestIsIndex:
    def test_get_root(self):
        request = MagicMock(method="GET", path="/")
        assert is_index(request) is True

    def test_post_root(self):
        request = MagicMock(method="POST", path="/")
        assert is_index(request) is False

    def test_get_other_path(self):
        request = MagicMock(method="GET", path="/about")
        assert is_index(request) is False


# ═══════════════════════════════════════════════════════════════════
# get_title
# ═══════════════════════════════════════════════════════════════════


class TestGetTitle:
    def test_value_error(self):
        assert get_title(ValueError("x")) == "Value Error"

    def test_match_not_found(self):
        from proper.errors import MatchNotFound

        assert get_title(MatchNotFound("x")) == "Match Not Found"


# ═══════════════════════════════════════════════════════════════════
# get_request_data
# ═══════════════════════════════════════════════════════════════════


class TestGetRequestData:
    def test_happy_path(self):
        request = MagicMock()
        request.query = {"a": "1"}
        request.form = {"b": "2"}
        request.headers = {"host": "localhost"}
        result = get_request_data(request)
        assert result["request_query"] == {"a": "1"}
        assert result["request_form"] == {"b": "2"}
        assert result["request_headers"] == {"host": "localhost"}

    def test_query_raises(self):
        request = MagicMock()
        type(request).query = PropertyMock(side_effect=Exception("bad query"))
        request.form = {}
        request.headers = {}
        result = get_request_data(request)
        assert result["request_query"] is None

    def test_form_raises(self):
        request = MagicMock()
        request.query = {}
        type(request).form = PropertyMock(side_effect=Exception("bad form"))
        request.headers = {}
        result = get_request_data(request)
        assert result["request_form"] is None

    def test_headers_raises(self):
        request = MagicMock()
        request.query = {}
        request.form = {}
        type(request).headers = PropertyMock(side_effect=Exception("bad headers"))
        result = get_request_data(request)
        assert result["request_headers"] is None

    def test_all_raise(self):
        request = MagicMock()
        type(request).query = PropertyMock(side_effect=Exception)
        type(request).form = PropertyMock(side_effect=Exception)
        type(request).headers = PropertyMock(side_effect=Exception)
        result = get_request_data(request)
        assert result == {
            "request_query": None,
            "request_form": None,
            "request_headers": None,
        }


# ═══════════════════════════════════════════════════════════════════
# fallback handlers
# ═══════════════════════════════════════════════════════════════════


class TestFallbackHandlers:
    def test_fallback_not_found(self):
        response = MagicMock()
        fallback_not_found_handler(response)
        assert response.body is not None

    def test_fallback_forbidden(self):
        response = MagicMock()
        fallback_forbidden_handler(response)
        assert response.body is not None

    def test_fallback_error(self):
        response = MagicMock()
        response.error = ValueError("crash")
        fallback_error_handler(response)
        assert response.body is not None


# ═══════════════════════════════════════════════════════════════════
# render_default_index
# ═══════════════════════════════════════════════════════════════════


class TestRenderDefaultIndex:
    def test_sets_body(self):
        request = MagicMock()
        request.scope = {}
        response = MagicMock()
        render_default_index(request, response)
        assert response.body is not None
        body = response.body
        assert isinstance(body, str)


# ═══════════════════════════════════════════════════════════════════
# debug_not_found_handler
# ═══════════════════════════════════════════════════════════════════


class TestDebugNotFoundHandler:
    def test_index_request_renders_default_page(self):
        app = MagicMock()
        request = MagicMock(method="GET", path="/")
        request.scope = {}
        response = MagicMock()

        debug_not_found_handler(app, request, response)
        # Should have rendered the default-index template
        body = response.body
        assert isinstance(body, str)

    def test_non_index_renders_not_found_page(self):
        app = MagicMock()
        app.config = {"DEBUG": True}
        app.routes = []
        request = MagicMock(method="GET", path="/missing")
        request.query = {}
        request.form = {}
        request.headers = {}
        response = MagicMock()
        response.error = Exception("not found")

        debug_not_found_handler(app, request, response)
        body = response.body
        assert isinstance(body, str)


# ═══════════════════════════════════════════════════════════════════
# debug_error_handler
# ═══════════════════════════════════════════════════════════════════


class TestDebugErrorHandler:
    def test_renders_error_page(self):
        app = MagicMock()
        app.config = {"DEBUG": True}
        request = MagicMock()
        request.query = {}
        request.form = {}
        request.headers = {}
        response = MagicMock()

        try:
            raise ValueError("boom")
        except ValueError as exc:
            response.error = exc
            debug_error_handler(app, request, response)

        body = response.body
        assert isinstance(body, str)
