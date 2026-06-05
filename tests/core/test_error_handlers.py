from unittest.mock import MagicMock, PropertyMock, patch

from proper.core.error_handlers import (
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
from proper.errors import MatchNotFound


def test_render_no_data_reads_raw_file():
    body = render("fallback-error.html")
    assert isinstance(body, str)
    assert len(body) > 0


def test_render_with_data_uses_jinja():
    body = render(
        "default-index.jx",
        proper_version="1.0",
        server_software="test",
        python_version="3.14",
    )
    assert "1.0" in body


def test_render_template_error_falls_back():
    with patch("proper.core.error_handlers.jinja_render", side_effect=Exception("boom")):
        body = render("debug-error.jx", some_data="x")
    # Should fall back to the static fallback-error.html
    assert isinstance(body, str)
    assert len(body) > 0


def test_redact_value_masks_after_four_chars():
    assert redact_value("abcdefgh") == "abcd▒▒▒▒"


def test_redact_value_short_value():
    assert redact_value("abcd") == "abcd"


def test_redacts_secret_keys():
    data = {"SECRET_KEYS": ["supersecretkey123"]}
    result = redact_sensitive_info(data)
    assert result["SECRET_KEYS"][0].startswith("supe")
    assert "▒" in result["SECRET_KEYS"][0]


def test_redacts_password():
    data = {"password": "mysecretpass"}
    result = redact_sensitive_info(data)
    assert result["password"].startswith("myse")
    assert "▒" in result["password"]


def test_leaves_non_sensitive_fields():
    data = {"DEBUG": True, "HOST": "localhost"}
    result = redact_sensitive_info(data)
    assert result["DEBUG"] is True
    assert result["HOST"] == "localhost"


def test_recurses_into_nested_dicts():
    data = {"DATABASES": {"main": {"password": "dbpass123"}}}
    result = redact_sensitive_info(data)
    assert "▒" in result["DATABASES"]["main"]["password"]


def test_no_secret_keys():
    data = {"DEBUG": False}
    result = redact_sensitive_info(data)
    assert result == {"DEBUG": False}


def test_falsy_password_not_redacted():
    data = {"password": ""}
    result = redact_sensitive_info(data)
    assert result["password"] == ""


def test_get_root():
    request = MagicMock(method="GET", path="/")
    assert is_index(request) is True


def test_post_root():
    request = MagicMock(method="POST", path="/")
    assert is_index(request) is False


def test_get_other_path():
    request = MagicMock(method="GET", path="/about")
    assert is_index(request) is False


def test_value_error():
    assert get_title(ValueError("x")) == "Value Error"


def test_match_not_found():
    assert get_title(MatchNotFound("x")) == "Match Not Found"


def test_happy_path():
    request = MagicMock()
    request.query = {"a": "1"}
    request.form = {"b": "2"}
    request.headers = {"host": "localhost"}
    result = get_request_data(request)
    assert result["request_query"] == {"a": "1"}
    assert result["request_form"] == {"b": "2"}
    assert result["request_headers"] == {"host": "localhost"}


def test_query_raises():
    request = MagicMock()
    type(request).query = PropertyMock(side_effect=Exception("bad query"))
    request.form = {}
    request.headers = {}
    result = get_request_data(request)
    assert result["request_query"] is None


def test_form_raises():
    request = MagicMock()
    request.query = {}
    type(request).form = PropertyMock(side_effect=Exception("bad form"))
    request.headers = {}
    result = get_request_data(request)
    assert result["request_form"] is None


def test_headers_raises():
    request = MagicMock()
    request.query = {}
    request.form = {}
    type(request).headers = PropertyMock(side_effect=Exception("bad headers"))
    result = get_request_data(request)
    assert result["request_headers"] is None


def test_all_raise():
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


def test_fallback_not_found():
    response = MagicMock()
    fallback_not_found_handler(response)
    assert response.body is not None


def test_fallback_forbidden():
    response = MagicMock()
    fallback_forbidden_handler(response)
    assert response.body is not None


def test_fallback_error():
    response = MagicMock()
    response.error = ValueError("crash")
    fallback_error_handler(response)
    assert response.body is not None


def test_sets_body():
    request = MagicMock()
    request.scope = {}
    response = MagicMock()
    render_default_index(request, response)
    assert response.body is not None
    body = response.body
    assert isinstance(body, str)


def test_index_request_renders_default_page():
    app = MagicMock()
    request = MagicMock(method="GET", path="/")
    request.scope = {}
    response = MagicMock()

    debug_not_found_handler(app, request, response)
    # Should have rendered the default-index template
    body = response.body
    assert isinstance(body, str)


def test_non_index_renders_not_found_page():
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


def test_renders_error_page():
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
