from unittest.mock import patch

import pytest

from proper import TestClient, current, status
from proper.constants import (
    FLASHES_SESSION_KEY,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SALT,
)
from proper.controller import Controller
from proper.core.response import Response
from proper.errors import MatchNotFound
from proper.helpers import DotDict
from proper.pipeline import (
    LOCAL_HOSTS,
    copy_session,
    dispatch,
    head_to_get,
    is_local_host,
    match,
    method_override,
    redirect,
    update_session_cookie,
)
from proper.router import Route
from proper.test_client import make_test_request


def _req(*, method="GET", url="/", headers=None, **kw):
    return make_test_request(url, method=method, headers=headers or [], **kw)


def _resp(*, app=None, **kw):
    return Response(app)


@pytest.fixture()
def make_co(app):
    def _make_co(*, method="GET", url="/", headers=None, **kw):
        request = make_test_request(
            url, method=method, headers=headers or [], app=app, **kw
        )
        response = Response(app)
        return Controller(request, response)
    return _make_co


@pytest.fixture()
def co(make_co):
    return make_co()


@pytest.fixture()
def client(app):
    return TestClient(app)



class TestHeadToGet:
    def test_rewrites_head_to_get(self, make_co):
        co = make_co(method="HEAD")
        head_to_get(co.request, None)
        assert co.request.method == "GET"

    def test_preserves_original_request_method(self, make_co):
        co = make_co(method="HEAD")
        head_to_get(co.request, None)
        assert co.request.request_method == "HEAD"

    def test_does_not_touch_get(self, co):
        head_to_get(co.request, None)
        assert co.request.method == "GET"

    def test_does_not_touch_post(self, make_co):
        co = make_co(method="POST")
        head_to_get(co.request, None)
        assert co.request.method == "POST"


class TestMethodOverride:
    def test_override_via_header(self, make_co):
        co = make_co(method="POST", headers=[("x-http-method-override", "PUT")])
        method_override(co.request, None)
        assert co.request.method == "PUT"

    def test_override_via_query_param(self, make_co):
        co = make_co(method="POST", url="/?_method=DELETE")
        method_override(co.request, None)
        assert co.request.method == "DELETE"

    def test_override_via_form_body(self, make_co):
        co = make_co(
            method="POST",
            headers=[("content-type", "application/x-www-form-urlencoded")],
        )
        co.request.form = {"_method": "PATCH"}
        method_override(co.request, None)
        assert co.request.method == "PATCH"

    def test_ignores_non_post(self, make_co):
        co = make_co(method="GET", headers=[("x-http-method-override", "PUT")])
        method_override(co.request, None)
        assert co.request.method == "GET"

    def test_ignores_invalid_override(self, make_co):
        co = make_co(method="POST", headers=[("x-http-method-override", "GET")])
        method_override(co.request, None)
        assert co.request.method == "POST"

    def test_override_to_query(self, make_co):
        co = make_co(method="POST", headers=[("x-http-method-override", "QUERY")])
        method_override(co.request, None)
        assert co.request.method == "QUERY"

    def test_case_insensitive_override(self, make_co):
        co = make_co(method="POST", headers=[("x-http-method-override", "put")])
        method_override(co.request, None)
        assert co.request.method == "PUT"



class TestMatch:
    def test_sets_matched_route_and_params(self, app, make_co):
        class Dummy(Controller):
            def index(self):
                pass

        app.router.add_route(Route(method="GET", path="/items/:id", to=Dummy.index))
        co = make_co(method="GET", url="/items/42")
        match(co.request, co.response)
        assert co.request.matched_route is not None
        assert co.request.matched_params["id"] == "42"

    def test_raises_on_no_match(self, app, make_co):
        co = make_co(method="GET", url="/nope")
        with pytest.raises(MatchNotFound):
            match(co.request, None)

    @pytest.mark.parametrize("host", LOCAL_HOSTS)
    def test_local_host_treated_as_none(self, app, make_co, host):
        class Dummy(Controller):
            def index(self):
                pass

        app.router.add_route(Route(method="GET", path="/ok", to=Dummy.index))
        co = make_co(method="GET", url="/ok", server=(host, 80))
        match(co.request, None)
        assert co.request.matched_route is not None


    @pytest.mark.parametrize(
        "host",
        [
            "localhost",
            "localhost.",
            "LOCALHOST",
            "127.0.0.1",
            "127.0.0.1.",
            "127.000.000.001",
            "127.1",
            "127.0.1",
            "127.255.255.254",
            "2130706433",
            "0x7f.0.0.1",
            "0x7F000001",
            "0177.0.0.1",
            "0177.0.0.1.",
            pytest.param("0x" + "0" * 5000 + "7f000001", id="0x0...07f000001"),
            pytest.param("0" * 5000 + "177.0.0.1", id="00...0177.0.0.1"),
            "%31%32%37.0.0.1",
            "%6Cocalhost",
            "0.0.0.0",
            "0",
            "0.0",
            "0x",
            "[::1]",
            "[0:0:0:0:0:0:0:1]",
            "[0000::0001]",
            "[::ffff:127.0.0.1]",
            "[::ffff:7f00:1]",
            "[::FFFF:127.1.2.3]",
            "[::]",
            "[0:0:0:0:0:0:0:0]",
            "[::ffff:0.0.0.0]",
            "127.0.0.1:8000",
            "[::1]:8000",
        ],
    )
    def test_every_spelling_of_a_local_host_matches_no_host_route(
        self, app, make_co, host
    ):
        class Dummy(Controller):
            def index(self):
                pass

        app.router.add_route(
            Route(method="GET", path="/ok", host=":h<.+>", to=Dummy.index)
        )
        co = make_co(method="GET", url="/ok", headers=[("host", host)])
        with pytest.raises(MatchNotFound):
            match(co.request, None)

    @pytest.mark.parametrize(
        "host",
        [
            "example.com",
            "localhost.example.com",
            "localhost..",
            "app.localhost",
            "127.0.0.1.example.com",
            "127.0.0.1..",
            "128.0.0.1",
            "126.255.255.255",
            "0.0.0.1",
            "1",
            "127.0.0.256",
            "127.0.0.1.1",
            "0x7g.0.0.1",
            "08.0.0.1",
            "127.0.0.1x",
            "1.2.3.4",
            "[::2]",
            "[::ffff:128.0.0.1]",
            "[::127.0.0.1]",
            "[fe80::1]",
            "%31%32%38.0.0.1",
            "127%3a0",
            "%3a%3a1.",
            "127..0.1",
        ],
    )
    def test_other_hosts_match_host_routes(self, app, make_co, host):
        class Dummy(Controller):
            def index(self):
                pass

        app.router.add_route(
            Route(method="GET", path="/ok", host=":h<.+>", to=Dummy.index)
        )
        co = make_co(method="GET", url="/ok", headers=[("host", host)])
        match(co.request, None)
        assert co.request.matched_route is not None

    @pytest.mark.parametrize(
        "host",
        [
            "111111111111",
            "4294967296",
            pytest.param("1" * 4301, id="1...1"),
            pytest.param("127.0.0." + "1" * 4301, id="127.0.0.1...1"),
        ],
    )
    def test_a_long_decimal_part_is_not_local(self, app, make_co, host):
        # `int` raises `ValueError` for a decimal text of more than 4300
        # digits; such a host is not an IPv4 address.
        class Dummy(Controller):
            def index(self):
                pass

        app.router.add_route(Route(method="GET", path="/ok", to=Dummy.index))
        assert is_local_host(host) is False
        co = make_co(method="GET", url="/ok", headers=[("host", host)])
        match(co.request, None)
        assert co.request.matched_route is not None


class TestRedirect:
    def test_returns_none_when_no_route(self, co):
        co.request.matched_route = None
        assert redirect(co.request, co.response) is None

    def test_returns_none_when_route_is_not_redirect(self, co):
        co.request.matched_route = Route(method="GET", path="/", to=lambda: None)
        assert redirect(co.request, co.response) is None

    def test_returns_response_when_redirect(self, co):
        route = Route(method="GET", path="/old", redirect="/new")
        co.request.matched_route = route
        co.request.matched_params = {}
        result = redirect(co.request, co.response)
        assert result is co.response
        assert co.response.status == status.temporary_redirect

    def test_redirect_interpolates_params(self, co):
        route = Route(method="GET", path="/old/:id", redirect="/new/{id}")
        co.request.matched_route = route
        co.request.matched_params = {"id": "42"}
        redirect(co.request, co.response)
        location = co.response.headers.get("Location")
        assert location == "/new/42"

    @pytest.mark.parametrize("value, location", [
        ("/evil.com", "/evil.com"),  # from /go//evil.com
        ("a\r\nSet-Cookie: x=1", "/a%0D%0ASet-Cookie:%20x=1"),
        ("100%", "/100%25"),
        ("a?b#c", "/a%3Fb%23c"),
    ])
    def test_redirect_encodes_params(self, co, value, location):
        route = Route(method="GET", path="/go/:p<path>", redirect="/{p}")
        co.request.matched_route = route
        co.request.matched_params = {"p": value}
        redirect(co.request, co.response)
        assert co.response.headers.get("Location") == location



class TestCopySession:
    def test_copies_session_from_cookie(self, app, make_co):
        co = make_co(method="GET")
        copy_session(co.request, co.response)
        assert co.request.session == {}
        assert co.response.session == {}

    def test_strips_flashes_from_response_session(self, app, make_co):
        session_data = {
            "user": "alice",
            FLASHES_SESSION_KEY: [("info", "saved!")],
        }
        with patch(
            "proper.pipeline._find_session_by_cookie",
            return_value=session_data,
        ):
            co = make_co(method="GET")
            copy_session(co.request, co.response)

        assert FLASHES_SESSION_KEY in co.request.session
        assert co.request.session[FLASHES_SESSION_KEY] == [("info", "saved!")]

        assert FLASHES_SESSION_KEY not in co.response.session
        assert co.response.session["user"] == "alice"

    def test_reads_the_session_from_a_signed_cookie(self, app, make_co):
        token = app.dumps({"user": "alice"}, salt=SESSION_COOKIE_SALT)
        co = make_co(headers=[("cookie", f"{SESSION_COOKIE_NAME}={token}")])
        copy_session(co.request, co.response)
        assert co.request.session == {"user": "alice"}
        assert co.response.session == {"user": "alice"}

    @pytest.mark.parametrize("data", ["alice", 42, True, [["user", "alice"]]])
    def test_a_session_cookie_that_is_not_an_object_is_no_session(
        self, app, make_co, data
    ):
        token = app.dumps(data, salt=SESSION_COOKIE_SALT)
        co = make_co(headers=[("cookie", f"{SESSION_COOKIE_NAME}={token}")])
        copy_session(co.request, co.response)
        assert co.request.session == {}
        assert co.response.session == {}

    def test_skips_for_options(self, app, make_co):
        co = make_co(method="OPTIONS")
        copy_session(co.request, co.response)
        assert co.request.session == {}



    def test_the_sessions_share_no_value_that_can_change(self, app, make_co):
        data = {"user": "alice", "cart": [1, 2], "prefs": {"theme": "dark", "tags": ["a"]}}
        token = app.dumps(data, salt=SESSION_COOKIE_SALT)
        co = make_co(headers=[("cookie", f"{SESSION_COOKIE_NAME}={token}")])
        copy_session(co.request, co.response)
        assert type(co.request.session) is dict
        assert co.response.session == co.request.session
        assert co.response.session["cart"] is not co.request.session["cart"]
        assert co.response.session["prefs"] is not co.request.session["prefs"]
        assert co.response.session["prefs"]["tags"] is not co.request.session["prefs"]["tags"]

    def test_without_a_cookie_the_sessions_are_apart(self, app, make_co):
        co = make_co(method="GET")
        copy_session(co.request, co.response)
        co.response.session["user"] = "alice"
        assert co.request.session == {}


class TestSessionChangesInPlace:
    """A list or a dict changed in place in `response.session` is a change:
    the cookie is written again."""

    @pytest.mark.parametrize("change", [
        lambda session: session["cart"].append(3),
        lambda session: session["prefs"].update(theme="light"),
        lambda session: session["prefs"]["tags"].append("b"),
    ])
    def test_a_change_in_place_is_saved(self, app, make_co, change):
        current.app = app
        data = {"cart": [1, 2], "prefs": {"theme": "dark", "tags": ["a"]}}
        token = app.dumps(data, salt=SESSION_COOKIE_SALT)
        co = make_co(headers=[("cookie", f"{SESSION_COOKIE_NAME}={token}")])
        copy_session(co.request, co.response)
        change(co.response.session)
        update_session_cookie(co.request, co.response)
        cookies = co.response.get_cookie_tuples()
        assert [c for c in cookies if SESSION_COOKIE_NAME in c[1]]


class TestUpdateSessionCookie:
    def test_no_cookie_when_session_unchanged(self, app, co):
        co.request.session = {"foo": "bar"}
        co.response.session = {"foo": "bar"}
        update_session_cookie(co.request, co.response)
        cookies = co.response.get_cookie_tuples()
        session_cookies = [c for c in cookies if SESSION_COOKIE_NAME in c[1]]
        assert session_cookies == []

    def test_sets_cookie_when_session_modified(self, app, co):
        current.app = app
        co.request.session = {}
        co.response.session = {"foo": "bar"}
        update_session_cookie(co.request, co.response)
        cookies = co.response.get_cookie_tuples()
        session_cookies = [c for c in cookies if SESSION_COOKIE_NAME in c[1]]
        assert len(session_cookies) == 1

    def test_unsets_cookie_when_session_cleared(self, app, co):
        co.request.session = {"foo": "bar"}
        co.response.session = {}
        update_session_cookie(co.request, co.response)
        cookies = co.response.get_cookie_tuples()
        session_cookies = [c for c in cookies if SESSION_COOKIE_NAME in c[1]]
        assert len(session_cookies) == 1
        cookie_val = session_cookies[0][1]
        assert "max-age=0" in cookie_val.lower() or "expires=" in cookie_val.lower()

    @pytest.mark.parametrize(
        "peer, secure",
        [
            (("127.0.0.1", 50000), True),  # a local reverse proxy
            (("203.0.113.5", 50000), False),  # a client sending the header itself
        ],
    )
    def test_secure_from_x_forwarded_proto_only_from_a_trusted_proxy(
        self, app, make_co, peer, secure
    ):
        co = make_co(headers=[("x-forwarded-proto", "https")], client=peer)
        co.response.session = {"foo": "bar"}
        update_session_cookie(co.request, co.response)
        cookies = co.response.get_cookie_tuples()
        session_cookie = [c for c in cookies if SESSION_COOKIE_NAME in c[1]][0][1]
        assert ("; Secure" in session_cookie) is secure


class TestFlashThroughPipeline:
    """A flash set by a controller (after `copy_session` has run) must end up
    in the session cookie, so the next request can read it back.
    """

    def test_flash_set_after_copy_session_persists_to_cookie(self, app, make_co):
        current.app = app
        co = make_co(method="POST")

        copy_session(co.request, co.response)
        co.response.flash.message("info", "Saved!")
        update_session_cookie(co.request, co.response)

        assert co.response.session.get(FLASHES_SESSION_KEY) == [("info", "Saved!")]

        cookies = co.response.get_cookie_tuples()
        session_cookies = [c for c in cookies if SESSION_COOKIE_NAME in c[1]]
        assert len(session_cookies) == 1, (
            "session cookie was not written, so the flash will be lost"
        )



class _DispatchHello(Controller):
    def index(self):
        return "hello"

    def show(self):
        return "page"


class TestDispatch:
    def test_dispatches_to_controller_action(self, app, co):
        route = Route(method="GET", path="/hello", to=_DispatchHello.index)
        co.request.matched_route = route
        co.request.matched_params = {}
        dispatch(co.request, co.response)
        assert co.response.body == "hello"

    def test_sets_matched_action(self, app, co):
        route = Route(method="GET", path="/page", to=_DispatchHello.show)
        co.request.matched_route = route
        co.request.matched_params = {}
        dispatch(co.request, co.response)
        assert co.request.matched_action == "show"



class GreetController(Controller):
    def index(self):
        return "hello"

    def show(self):
        name = self.params.get("name", "world")
        return f"hello {name}"

    def create(self):
        return "created"

    def update(self):
        return f"updated via {self.request.method}"

    def explode(self):
        raise ValueError("boom")

    def unchanged(self):
        # No view exists for this action: a 304 renders none.
        self.response.status = status.not_modified



class SessionController(Controller):
    def write_session(self):
        self.response.session["color"] = "blue"
        return "ok"

    def read_session(self):
        return self.response.session.get("color", "none")



class TestPipeline:
    def test_happy_path(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        result = client.get("/hello")
        assert result.status == status.ok
        assert result.body == "hello"

    def test_a_host_with_a_long_decimal_part(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        result = client.get("/hello", headers={"host": "1" * 8000})
        assert result.status == status.ok
        assert result.body == "hello"

    def test_with_path_params(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/hello/:name", to=GreetController.show)
        )
        result = client.get("/hello/alice")
        assert result.status == status.ok
        assert result.body == "hello alice"

    def test_with_path_params_from_url_for(self, app, client):
        # The params arrive decoded, as from a server.
        app.router.add_route(
            Route(
                method="GET", path="/hello/:name", name="hello", to=GreetController.show
            )
        )
        result = client.get(app.url_for("hello", DotDict(name="café & co?#a%20b")))
        assert result.status == status.ok
        assert result.body == "hello café & co?#a%20b"

    def test_not_modified_set_by_the_action_renders_no_view(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/unchanged", to=GreetController.unchanged)
        )
        result = client.get("/unchanged")
        assert result.status == status.not_modified
        assert result.body == ""

    def test_head_returns_empty_body(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        result = client.head("/hello")
        assert result.status == status.ok
        assert result.body == ""

    def test_post_overridden_to_put(self, app, client):
        app.router.add_route(
            Route(method="PUT", path="/items", to=GreetController.update)
        )
        result = client.post("/items?_method=PUT")
        assert result.status == status.ok
        assert result.body == "updated via PUT"

    def test_post_overridden_via_header(self, app, client):
        app.router.add_route(
            Route(method="PATCH", path="/items", to=GreetController.update)
        )
        result = client.post(
            "/items",
            headers={"x-http-method-override": "PATCH"},
        )
        assert result.status == status.ok
        assert result.body == "updated via PATCH"

    def test_404_for_unmatched_route(self, client):
        result = client.get("/nonexistent")
        assert result.status == status.not_found

    def test_redirect_route(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/old", redirect="/new")
        )
        result = client.get("/old")
        assert result.status == status.temporary_redirect
        assert result.headers.get("location") == "/new"

    def test_redirect_with_params(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/old/:id", redirect="/new/{id}")
        )
        result = client.get("/old/99")
        assert result.status == status.temporary_redirect
        assert result.headers.get("location") == "/new/99"

    def test_on_teardown_always_runs(self, app, client):
        called = []
        app.on_teardown(lambda: called.append("teardown"))
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        client.get("/hello")
        assert called == ["teardown"]

    def test_on_teardown_runs_on_error(self, app, client):
        called = []
        app.on_teardown(lambda: called.append("teardown"))
        app.router.add_route(
            Route(method="GET", path="/explode", to=GreetController.explode)
        )
        client.get("/explode")
        assert "teardown" in called

    def test_on_error_runs_on_exception(self, app, client):
        called = []
        app.on_error(lambda: called.append("error"))
        app.router.add_route(
            Route(method="GET", path="/explode", to=GreetController.explode)
        )
        client.get("/explode")
        assert "error" in called

    def test_on_error_not_called_on_success(self, app, client):
        called = []
        app.on_error(lambda: called.append("error"))
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        client.get("/hello")
        assert called == []

    def test_around_request_wraps_the_request(self, app, client):
        called = []

        @app.around_request
        def outer(request, response, call_next):
            called.append(("outer", request.path))
            response = call_next(request, response)
            called.append(("outer", response.body))
            return response

        @app.around_request
        def inner(request, response, call_next):
            called.append(("inner", current.response is response))
            return call_next(request, response)

        app.on_teardown(lambda: called.append(("teardown", None)))
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        result = client.get("/hello")
        assert result.body == "hello"
        assert called == [
            ("outer", "/hello"),
            ("inner", True),
            ("teardown", None),
            ("outer", "hello"),
        ]

    def test_around_request_returns_the_function(self, app):
        def hook(request, response, call_next):
            return call_next(request, response)

        assert app.around_request(hook) is hook

    def test_around_request_sees_handled_errors(self, app, client):
        seen = []

        @app.around_request
        def hook(request, response, call_next):
            response = call_next(request, response)
            seen.append(response.error)
            return response

        app.router.add_route(
            Route(method="GET", path="/explode", to=GreetController.explode)
        )
        result = client.get("/explode")
        assert result.status == status.internal_server_error
        assert isinstance(seen[0], ValueError)

    def test_around_request_sees_unhandled_errors(self, app, client):
        app.config.CATCH_ALL_ERRORS = False
        seen = []

        @app.around_request
        def hook(request, response, call_next):
            try:
                return call_next(request, response)
            except ValueError as error:
                seen.append(error)
                raise

        app.router.add_route(
            Route(method="GET", path="/explode", to=GreetController.explode)
        )
        with pytest.raises(ValueError):
            client.get("/explode")
        assert len(seen) == 1

    def test_around_request_can_replace_the_response(self, app, client):
        @app.around_request
        def hook(request, response, call_next):
            call_next(request, response)
            response.body = "replaced"
            return response

        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        assert client.get("/hello").body == "replaced"

    def test_redirect_stops_pipeline(self, app, client):
        """A redirect route should never reach dispatch."""
        app.router.add_route(
            Route(method="GET", path="/redir", redirect="/target")
        )
        result = client.get("/redir")
        assert result.status == status.temporary_redirect
        # Body is the redirect HTML, not a controller response
        assert "hello" not in (result.body or "")
