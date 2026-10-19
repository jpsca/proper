import sys
import time
from collections import namedtuple
from importlib.metadata import version
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from proper import App, Controller, Route, TestClient
from proper.core.error_handlers import (
    MAX_REDACT_DEPTH,
    MAX_REDACT_VALUES,
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
from proper.test_client import make_test_request


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


def test_redact_value_of_a_value_that_is_not_a_string():
    assert redact_value(["hunter2", "s3cret"]) == "['hu" + "▒" * 17
    assert redact_value(12345678) == "1234▒▒▒▒"
    assert redact_value(1234.5678) == "1234▒▒▒▒▒"
    assert redact_value(b"abcdefgh") == "b'ab▒▒▒▒▒▒▒"


def test_redact_value_of_a_value_whose_str_raises():
    class Bad:
        def __str__(self):
            raise RuntimeError("no")

    assert redact_value(Bad()) == "▒▒▒▒"


def test_redacts_a_password_that_is_not_a_string():
    # A list was shown as it was, and an int or float raised in redact_value.
    data = {
        "password": ["hunter2", "s3cret"],
        "DB": {"PASSWORD": 12345678, "Password": 1234.5678, "pw": ("abc",)},
    }
    result = redact_sensitive_info(data)
    assert result["password"] == ["hunt▒▒▒", "s3cr▒▒"]
    assert result["DB"]["PASSWORD"] == "1234▒▒▒▒"
    assert result["DB"]["Password"] == "1234▒▒▒▒▒"
    assert result["DB"]["pw"] == ("abc",)
    assert "hunter2" not in str(result) and "5678" not in str(result)


def test_redacts_secret_keys_that_are_not_a_list_of_strings():
    data = {"SECRET_KEYS": ("supersecretkey123", b"bytessecret", 123456789)}
    assert redact_sensitive_info(data)["SECRET_KEYS"] == (
        "supe" + "▒" * 13,
        "b'by" + "▒" * 10,
        "1234" + "▒" * 5,
    )
    assert redact_sensitive_info({"SECRET_KEYS": "supersecretkey123"}) == {
        "SECRET_KEYS": "supe" + "▒" * 13
    }
    assert redact_sensitive_info({"SECRET_KEYS": [["nestedsecret"]]}) == {
        "SECRET_KEYS": [["nest" + "▒" * 8]]
    }


def test_redacts_everything_under_a_sensitive_key():
    # A dict under SECRET_KEYS or a password key was copied with only its
    # own `password` keys redacted, so these were shown in clear.
    assert redact_sensitive_info({"SECRET_KEYS": {"old": "supersecretvalue1"}}) == {
        "SECRET_KEYS": {"old": "supe" + "▒" * 13}
    }
    data = {
        "DB": {
            "password": {
                "db": "hunter2hunter2",
                "more": [{"x": "abcdefgh"}, ("ijklmnop", 123456789)],
                "empty": "",
                "none": None,
            },
            "host": "localhost",
        }
    }
    assert redact_sensitive_info(data) == {
        "DB": {
            "password": {
                "db": "hunt" + "▒" * 10,
                "more": [{"x": "abcd▒▒▒▒"}, ("ijkl▒▒▒▒", "1234▒▒▒▒▒")],
                "empty": "",
                "none": None,
            },
            "host": "localhost",
        }
    }


def test_redacts_password_keys_in_dicts_inside_lists_and_tuples():
    # The dicts inside a list were not looked into.
    data = {
        "DATABASES": [{"password": "hunter2hunter2", "host": "db1"}],
        "REPLICAS": ({"name": "r", "creds": [{"PASSWORD": "s3cret-s3cret"}]},),
        "HOSTS": ["localhost", "example.com"],
    }
    assert redact_sensitive_info(data) == {
        "DATABASES": [{"password": "hunt" + "▒" * 10, "host": "db1"}],
        "REPLICAS": ({"name": "r", "creds": [{"PASSWORD": "s3cr" + "▒" * 9}]},),
        "HOSTS": ["localhost", "example.com"],
    }


def test_redact_keeps_keys_that_are_not_strings():
    data = {1: "one", ("a", "b"): {"password": "mysecretpass"}}
    result = redact_sensitive_info(data)
    assert result[1] == "one"
    assert result[("a", "b")]["password"] == "myse" + "▒" * 8


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
    request = make_test_request("/")
    request.server_software = "gunicorn/23.0.0"
    response = MagicMock()
    render_default_index(request, response)
    assert response.body is not None
    body = response.body
    assert isinstance(body, str)
    assert f"Proper Web Framework {version('proper')}" in body
    assert "<strong>Server:</strong> gunicorn/23.0.0" in body


def test_default_page_without_the_name_of_the_server():
    request = make_test_request("/")
    response = MagicMock()
    render_default_index(request, response)
    assert "Proper Web Framework" in response.body
    assert "Server:" not in response.body


def test_index_request_renders_default_page():
    app = MagicMock()
    request = make_test_request("/")
    response = MagicMock()

    debug_not_found_handler(app, request, response)
    # Should have rendered the default-index template
    body = response.body
    assert isinstance(body, str)
    assert "Proper Web Framework" in body


def test_new_app_shows_the_default_page():
    """Regression: the default page of an app without a route for "/"
    failed with a real request, and the app answered with an error."""
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": True})

    response = TestClient(app).get("/")

    assert response.status == 404
    assert "Proper Web Framework" in response.body


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


# --- Values that can't be rebuilt or read ---

Point = namedtuple("Point", "host port")


class Unreadable:
    def __bool__(self):
        raise RuntimeError("no bool")

    def __str__(self):
        raise RuntimeError("no str")


class BrokenDict(dict):
    def items(self):
        raise RuntimeError("no items")


class BrokenList(list):
    def __iter__(self):
        raise RuntimeError("no iter")


class BrokenKey:
    def __eq__(self, other):
        raise RuntimeError("no eq")

    def __hash__(self):
        return 1


def test_redact_named_tuples_become_dicts_and_tuple_subclasses_tuples():
    # `type(value)(generator)` raised TypeError for a named tuple and for
    # `sys.version_info`, so every debug page failed. A named tuple is now
    # a dict of its fields, so a `password` field is redacted.
    data = {
        "DB": Point("db.example.com", 5432),
        "VERSION": sys.version_info,
        "password": Point("hunter2hunter2", 12345678),
        "SECRET_KEYS": Point("supersecretkey123", "anothersecret"),
        "NESTED": [{"password": sys.version_info}],
    }
    result = redact_sensitive_info(data)
    assert result["DB"] == {"host": "db.example.com", "port": 5432}
    assert type(result["DB"]) is dict
    assert result["VERSION"] == tuple(sys.version_info)
    assert type(result["VERSION"]) is tuple
    assert result["password"] == {"host": "hunt" + "▒" * 10, "port": "1234▒▒▒▒"}
    assert result["SECRET_KEYS"] == {
        "host": "supe" + "▒" * 13,
        "port": "anot" + "▒" * 9,
    }
    assert type(result["NESTED"][0]["password"]) is tuple


def test_redacts_a_password_field_of_a_named_tuple():
    Creds = namedtuple("Creds", "user password SECRET_KEYS")
    data = {"DB": [Creds("admin", "hunter2hunter2", ("supersecretkey123",))]}
    assert redact_sensitive_info(data) == {
        "DB": [
            {
                "user": "admin",
                "password": "hunt" + "▒" * 10,
                "SECRET_KEYS": ("supe" + "▒" * 13,),
            }
        ]
    }


def timed_redact(data):
    start = time.perf_counter()
    result = redact_sensitive_info(data)
    assert time.perf_counter() - start < 1
    return result


def test_redact_shows_a_cycle_as_the_mask():
    # With two references to itself, each level doubled the work, and the
    # catch of RecursionError made it go on for ever.
    a = []
    a.extend([a, a])
    d = {}
    d["k0"] = d["k1"] = d
    d["password"] = "hunter2hunter2"
    result = timed_redact({"A": a, "D": d, "password": [a, d]})
    assert result["A"] == ["▒▒▒▒", "▒▒▒▒"]
    assert result["D"] == {"k0": "▒▒▒▒", "k1": "▒▒▒▒", "password": "hunt" + "▒" * 10}
    assert result["password"] == [
        ["▒▒▒▒", "▒▒▒▒"],
        {
            "k0": "▒▒▒▒",
            "k1": "▒▒▒▒",
            "password": "hunt" + "▒" * 10,
        },
    ]
    # A container shared by two branches, but not a cycle, is shown twice.
    shared = ["x"]
    assert timed_redact({"S": [shared, shared]}) == {"S": [["x"], ["x"]]}


def test_redact_shows_containers_below_the_depth_cap_as_the_mask():
    deep = "bottom"
    for _ in range(100):
        deep = [deep]
    result = timed_redact({"DEEP": deep})
    level = result["DEEP"]
    for _ in range(MAX_REDACT_DEPTH - 1):
        assert isinstance(level, list) and len(level) == 1
        level = level[0]
    assert level == "▒▒▒▒"


def test_redact_reads_a_bounded_number_of_values():
    # Shared lists, no cycle: 2 ** 31 paths without the value limit.
    level = ["x"]
    for _ in range(30):
        level = [level, level]
    result = timed_redact({"WIDE": level, "password": "hunter2hunter2"})
    assert "▒▒▒▒" in str(result["WIDE"])
    # The values after the limit are masked too, also the ones that are not
    # secret.
    assert result["password"] == "▒▒▒▒"
    many = {"MANY": list(range(MAX_REDACT_VALUES * 2))}
    values = timed_redact(many)["MANY"]
    assert values[:3] == [0, 1, 2]
    assert values[-1] == "▒▒▒▒"


def test_redact_never_raises():
    data = {
        "a": Unreadable(),
        "password": Unreadable(),
        "SECRET_KEYS": [Unreadable(), "supersecretkey123"],
        "b": BrokenDict(x=1),
        "c": [BrokenDict(x=1)],
        "d": BrokenList([1]),
        "password2": {"password": BrokenList([1])},
    }
    result = redact_sensitive_info(data)
    # An ordinary value is kept as it is, unread.
    assert result["a"] is data["a"]
    assert result["password"] == "▒▒▒▒"
    assert result["SECRET_KEYS"] == ["▒▒▒▒", "supe" + "▒" * 13]
    assert result["b"] == "▒▒▒▒"
    assert result["c"] == ["▒▒▒▒"]
    assert result["d"] == "▒▒▒▒"
    assert result["password2"] == {"password": "▒▒▒▒"}
    key = BrokenKey()
    assert redact_sensitive_info({key: "x"}) == {key: "▒▒▒▒"}
    assert redact_sensitive_info(BrokenDict(x=1)) == {}


def _cycle():
    a = []
    a.extend([a, a])
    return a


def _deep():
    deep = []
    for _ in range(100):
        deep = [deep, deep]
    return deep


@pytest.mark.parametrize(
    "value",
    [
        Point("h", 1),
        sys.version_info,
        {"password": Point("hunter2hunter2", 1)},
        _cycle(),
        _deep(),
    ],
)
def test_debug_pages_render_with_tuple_subclasses_in_the_config(value):
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": True})
    # Set after loading: the config loader copies values, and
    # `sys.version_info` can't be copied.
    app.config["DB"] = value
    app.config["OTHER"] = [value]
    client = TestClient(app, raise_server_errors=False)

    response = client.get("/nope")
    assert response.status == 404
    assert "Not Found" in response.body or "not match" in response.body

    app.router.add_route(Route("GET", "/boom", to=BoomController.boom))
    response = client.get("/boom")
    assert response.status == 500
    assert "boom" in response.body


class BoomController(Controller):
    def boom(self):
        raise ValueError("boom")
