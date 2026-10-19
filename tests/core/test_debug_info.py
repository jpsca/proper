import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from proper import App, Controller, Route, TestClient
from proper.core.debug_info import (
    MASK,
    ErrorInfo,
    Frame,
    describe_request,
    format_text,
    get_errors,
    hide_url_passwords,
    is_sensitive,
    safe_repr,
)
from proper.errors import NotFound
from proper.test_client import make_test_request


def _raise(error):
    raise error


def _caught(func, *args):
    try:
        func(*args)
    except Exception as error:
        return error
    raise AssertionError("it didn't raise")


def _total(items):
    api_key = "sk-1234567890"  # noqa: F841
    prices = dict.fromkeys(items, 1)
    return sum(prices[name] for name in ["a", "zzz"])


# --- Secrets ---


@pytest.mark.parametrize(
    "name",
    [
        "password",
        "DATABASE_PASSWORD",
        "SECRET_KEYS",
        "STRIPE_SECRET_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "github_token",
        "x-api-key",
        "Cookie",
        "authorization",
        "Proxy-Authorization",
    ],
)
def test_names_of_secrets(name):
    assert is_sensitive(name)


@pytest.mark.parametrize(
    "name",
    ["AUTH_TOKEN_LIFE", "AUTH_PASSWORD_MINLEN", "pw", "HOST", "AWS_ACCESS_KEY_ID", 1, None],
)
def test_names_that_are_not_of_secrets(name):
    assert not is_sensitive(name)


def test_the_password_of_a_url_is_hidden():
    text = "postgres://app:hunter2@db:5432/main and redis://cache:6379"
    assert hide_url_passwords(text) == f"postgres://app:{MASK}@db:5432/main and redis://cache:6379"


def test_safe_repr():
    assert "..." in safe_repr("x" * 500)
    assert len(safe_repr("x" * 500)) < 200
    assert safe_repr({"dsn": "mysql://root:toor@localhost/db"}) == f"{{'dsn': 'mysql://root:{MASK}@localhost/db'}}"

    class Bad:
        def __repr__(self):
            raise RuntimeError("no repr")

    assert safe_repr(Bad()).startswith("<Bad instance at 0x")


# --- The error and its frames ---


def test_the_frames_of_the_app_have_their_code_and_variables():
    error = _caught(_total, ["a"])
    (info,) = get_errors(error)

    assert info.type == "KeyError"
    assert info.message == "'zzz'"
    assert info.summary == "KeyError: 'zzz'"
    where = info.where
    assert where.name == "<genexpr>"
    assert where.path == "tests/core/test_debug_info.py"
    assert where.line == 'return sum(prices[name] for name in ["a", "zzz"])'
    assert (where.lineno, '    return sum(prices[name] for name in ["a", "zzz"])') in where.context
    assert len(where.context) == 6
    # `.0`, the iterator of the generator, is left out
    assert where.variables == {"name": "'zzz'", "prices": "{'a': 1}"}

    total = info.frames[-2]
    assert total.name == "_total"
    assert total.variables["api_key"] == MASK
    assert total.variables["items"] == "['a']"


def test_the_frames_of_proper_and_of_the_libraries_are_told_apart():
    app = App(__name__, {"SECRET_KEYS": ["*" * 50]})
    error = _caught(app.url_for, "Nope.index")
    (info,) = get_errors(error)

    assert info.frames[0].is_app
    assert info.frames[0].name == "_caught"
    proper_frames = info.frames[1:]
    assert proper_frames and not any(frame.is_app for frame in proper_frames)
    assert all(frame.context == [] and frame.variables == {} for frame in proper_frames)
    assert info.where is info.frames[0]
    groups = info.groups()
    assert groups[0] is info.frames[0]
    assert groups[1] == proper_frames


def test_when_no_frame_is_of_the_app_all_are_shown():
    # The traceback of an error raised in a thread of the pool starts in
    # the standard library
    with ThreadPoolExecutor(1) as pool:
        error = pool.submit(json.loads, "nope").exception()
    (info,) = get_errors(error)

    assert info.frames
    assert all(frame.is_app and frame.context for frame in info.frames)
    assert info.frames[-1].path.endswith("json/decoder.py")
    assert Path(info.frames[-1].path).is_absolute()  # outside the current folder


def test_a_frame_without_its_source():
    code = compile("raise ValueError('lost')", "/nowhere/lost.py", "exec")
    error = _caught(exec, code)
    (info,) = get_errors(error)

    lost = info.frames[-1]
    assert lost.path == "/nowhere/lost.py"
    assert lost.line == ""
    assert lost.context == []
    assert "At /nowhere/lost.py:1, in <module>\n\n  func = " in format_text([info])


def test_a_frame_of_code_with_no_file():
    error = _caught(exec, "raise ValueError('no file')")
    (info,) = get_errors(error)
    assert not info.frames[-1].is_app


def test_errors_chained_with_from_and_while_handling():
    def handling():
        try:
            _raise(KeyError("first"))
        except KeyError as first:
            raise RuntimeError("second") from first

    def while_handling():
        try:
            handling()
        except RuntimeError:
            _raise(NotFound("third"))

    errors = get_errors(_caught(while_handling))

    assert [err.summary for err in errors] == [
        "KeyError: 'first'",
        "RuntimeError: second",
        "proper.errors.NotFound: third",
    ]
    assert [err.chain for err in errors] == ["cause", "context", ""]
    text = format_text(errors)
    assert "The above exception was the direct cause of the following exception:" in text
    assert "During handling of the above exception, another exception occurred:" in text
    assert text.startswith("proper.errors.NotFound: third\n")


def test_a_suppressed_context_is_left_out():
    def suppressed():
        try:
            _raise(KeyError("first"))
        except KeyError:
            raise RuntimeError("second") from None

    errors = get_errors(_caught(suppressed))
    assert [err.type for err in errors] == ["RuntimeError"]


def test_an_error_that_is_its_own_context():
    error = ValueError("loop")
    error.__context__ = error
    assert len(get_errors(error)) == 1


def test_the_name_of_a_class_of_main_and_a_message_that_raises():
    class Odd(Exception):
        def __str__(self):
            raise RuntimeError("no str")

    Odd.__module__ = "__main__"
    (info,) = get_errors(Odd())
    assert info.type == "test_the_name_of_a_class_of_main_and_a_message_that_raises.<locals>.Odd"
    assert info.message == MASK
    assert info.frames == []
    assert info.where is None


def test_a_summary_without_a_message():
    assert ErrorInfo(type="KeyError", message="", frames=[]).summary == "KeyError"


# --- The text ---


def test_the_text_of_an_error():
    info = ErrorInfo(
        type="KeyError",
        message="'zzz'",
        frames=[
            Frame(path="proper/app.py", lineno=10, name="dispatch", line="co._call()", is_app=False),
            Frame(path="proper/app.py", lineno=20, name="_call", line="action()", is_app=False),
            Frame(
                path="myapp/controllers/order.py",
                lineno=8,
                name="create",
                line="return prices['zzz']",
                context=[(7, "def create(self):"), (8, "    return prices['zzz']")],
                variables={"prices": "{}"},
            ),
        ],
    )
    assert format_text([info]) == (
        "KeyError: 'zzz'\n"
        "\n"
        "At myapp/controllers/order.py:8, in create\n"
        "    7 | def create(self):\n"
        "  > 8 |     return prices['zzz']\n"
        "\n"
        "  prices = {}\n"
        "\n"
        "Traceback (most recent call last):\n"
        "  ... 2 frames of Proper or libraries ...\n"
        "  myapp/controllers/order.py:8, in create\n"
        "    return prices['zzz']\n"
        "KeyError: 'zzz'\n"
    )


def test_the_text_of_one_frame_of_proper():
    info = ErrorInfo(
        type="KeyError",
        message="x",
        frames=[Frame(path="proper/app.py", lineno=10, name="dispatch", line="", is_app=False)],
    )
    assert "  ... 1 frame of Proper or libraries ...\n" in format_text([info])


def test_the_text_tells_the_request_and_its_form():
    request = make_test_request("/orders?ref=x", method="POST")
    request.form = {"qty": "2", "password": "hunter2", "token": ""}
    request.matched_route = Route("POST", "orders", to=OrderController.create)

    text = format_text([ErrorInfo(type="KeyError", message="x", frames=[])], request)

    assert text.startswith("KeyError: x\n\nPOST /orders?ref=x -> OrderController.create\nForm data: {")
    assert f"'password': '{MASK}'" in text
    assert "'qty': '2'" in text
    assert "'token': ''" in text
    assert "hunter2" not in text
    assert text.endswith("\n\nTraceback (most recent call last):\nKeyError: x\n")


def test_describe_request():
    request = make_test_request("/go?next=https://u:p@x.com/")
    assert describe_request(request) == f"GET /go?next=https://u:{MASK}@x.com/"

    request.matched_route = Route("GET", "go", redirect="/elsewhere")
    assert describe_request(request) == f"GET /go?next=https://u:{MASK}@x.com/"

    assert describe_request(object()) == ""


def test_the_text_of_a_request_whose_form_raises():
    class Request:
        method = "GET"
        path = "/"
        query_string = ""
        matched_route = None

        @property
        def form(self):
            raise ValueError("bad body")

    text = format_text([ErrorInfo(type="E", message="", frames=[])], Request())
    assert text == "E\n\nGET /\n\nTraceback (most recent call last):\nE\n"


# --- The pages ---


class OrderController(Controller):
    def create(self):
        items = ["a"]
        return _total(items)

    def show(self):
        raise ValueError(self.params.get("q"))

    def chained(self):
        try:
            raise KeyError("first")
        except KeyError as first:
            raise RuntimeError("second") from first

    def handling(self):
        try:
            raise KeyError("first")
        except KeyError:
            raise RuntimeError("second")  # noqa: B904


@pytest.fixture()
def client():
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": True, "DB_PASSWORD": "hunter2hunter2"})
    app.router.add_route(Route("POST", "orders", to=OrderController.create, name="Order.create"))
    app.router.add_route(Route("GET", "orders/:id", to=OrderController.show))
    app.router.add_route(Route("GET", "old", redirect="/orders"))
    app.router.add_route(Route("", "build-only", name="Build"))
    return TestClient(app, raise_server_errors=False)


def test_the_error_page_of_a_tool_or_agent_is_text(client):
    result = client.post("/orders", body={"password": "hunter2"})

    assert result.status == 500
    assert result.mimetype == "text/plain"
    assert result.body.startswith(
        "KeyError: 'zzz'\n\nPOST /orders -> OrderController.create\n"
        f"Form data: {{'password': '{MASK}'}}\n\nAt tests/core/test_debug_info.py:"
    )
    assert "hunter2" not in result.body


def test_the_error_page_of_an_api_client_is_json(client):
    result = client.post("/orders", headers={"accept": "application/json"})

    assert result.mimetype == "application/json"
    data = json.loads(result.body)
    assert data["error"] == "KeyError"
    assert data["message"] == "'zzz'"
    assert data["details"].startswith("KeyError: 'zzz'\n")


def test_the_error_page_of_a_browser(client):
    result = client.post(
        "/orders",
        body={"password": "hunter2"},
        headers={"accept": "text/html,application/xhtml+xml,*/*;q=0.8", "cookie": "sid=abcdefgh"},
    )

    assert result.mimetype == "text/html"
    body = result.body
    assert '<p class="kind">KeyError</p>' in body
    assert "<h1>&#39;zzz&#39;</h1>" in body
    assert "POST /orders -&gt; OrderController.create" in body
    assert '<details class="frame where" open>' in body
    assert "frames of Proper or libraries" in body
    assert '<span class="hl">' in body
    assert '<textarea id="error-text" hidden readonly>KeyError: &#39;zzz&#39;' in body
    for secret in ("hunter2", "abcdefgh"):
        assert secret not in body


def test_the_error_page_escapes_what_it_shows(client):
    result = client.get(
        "/orders/1", params={"q": "<script>alert(1)</script>"}, headers={"accept": "text/html"}
    )
    assert "<script>alert(1)</script>" not in result.body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result.body


def test_the_page_of_a_chained_error(client):
    client.app.router.add_route(Route("GET", "chained", to=OrderController.chained))
    body = client.get("/chained", headers={"accept": "text/html"}).body
    assert "It was raised because of this one:" in body
    assert "<code>KeyError: &#39;first&#39;</code>" in body


def test_the_page_of_an_error_raised_while_handling_another(client):
    client.app.router.add_route(Route("GET", "handling", to=OrderController.handling))
    body = client.get("/handling", headers={"accept": "text/html"}).body
    assert "It was raised while handling this one:" in body


def test_the_not_found_page_of_a_tool_or_agent_is_text(client):
    result = client.get("/nope")

    assert result.status == 404
    assert result.mimetype == "text/plain"
    assert result.body == (
        "MatchNotFound: GET `/nope` does not match.\n"
        "\n"
        "Routes, in the order they are matched:\n"
        "  POST  /orders      Order.create  OrderController.create\n"
        "  GET   /orders/:id  Order.show    OrderController.show\n"
        "  GET   /old                       -> /orders\n"
    )


def test_the_not_found_page_of_an_api_client_is_json(client):
    result = client.get("/nope", headers={"accept": "application/vnd.api+json"})

    data = json.loads(result.body)
    assert data["error"] == "MatchNotFound"
    assert "Routes, in the order they are matched:" in data["details"]


def test_the_not_found_page_of_a_browser(client):
    result = client.get("/nope?q=<b>", headers={"accept": "text/html"})

    assert result.mimetype == "text/html"
    assert '<p class="kind">MatchNotFound</p>' in result.body
    assert "GET /nope?q=&lt;b&gt;" in result.body
    assert '<tr class="build-only" title="Build-only">' in result.body
    assert "↪ /orders" in result.body


def test_the_format_of_a_request_whose_accept_header_raises():
    from proper.core.error_handlers import wanted_format

    class Request:
        @property
        def accept(self):
            raise ValueError("bad header")

    assert wanted_format(Request()) == "text"


def test_the_format_of_a_request_that_accepts_neither_html_nor_json():
    from proper.core.error_handlers import wanted_format

    assert wanted_format(make_test_request(headers={"accept": "image/png, */*"})) == "text"


def test_the_text_of_a_frame_without_variables():
    frame = Frame(path="a.py", lineno=1, name="f", line="x()", context=[(1, "x()")])
    text = format_text([ErrorInfo(type="E", message="", frames=[frame])])
    assert "At a.py:1, in f\n  > 1 | x()\n\nTraceback" in text
