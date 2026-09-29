import re

import pytest

from proper import Route, Router
from proper.compile.routes import (
    Bucketed,
    Combined,
    Hosted,
    RouteTable,
    _first_literal_segment,
    _rename_groups,
    bucket,
    combine,
    lower_routes,
)
from proper.errors import MatchNotFound, MethodNotAllowed


class ItemController:
    def show(self):
        pass


def _route(method, path, name=None, host=None):
    return Route(method, path, name=name or path, host=host, redirect="/x")


class TestRenameGroups:
    def test_named_groups_and_backreferences(self):
        pattern = r"(?P<a>x)(?P=a)(?P<b_1>y)"
        assert _rename_groups(pattern, "r3_") == r"(?P<r3_a>x)(?P=r3_a)(?P<r3_b_1>y)"

    def test_leaves_the_rest_alone(self):
        pattern = r"(?:x)(?=y)(?!z)(?<=w)\(\?P<n>"
        assert _rename_groups(pattern, "r0_") == pattern


class TestCombine:
    def test_one_regex_in_registration_order(self):
        routes = [
            _route("GET", "posts/:id<int>"),
            _route("GET", "posts/:slug"),
            _route("GET", "files/:file<path>"),
        ]
        combined = combine(routes)
        assert isinstance(combined, Combined)
        assert combined.routes == tuple(routes)
        assert combined.groups == (
            (("id", "r0_id", int),),
            (("slug", "r1_slug", None),),
            (("file", "r2_file", None),),
        )
        assert combined.lookup("/posts/12", None) == (routes[0], {"id": 12})
        assert combined.lookup("/posts/hello", None) == (routes[1], {"slug": "hello"})
        assert combined.lookup("/posts/12/", None) == (routes[0], {"id": 12})
        assert combined.lookup("/files/a/b/c.txt", None) == (routes[2], {"file": "a/b/c.txt"})
        assert combined.lookup("/nope/12", None) is None

    def test_first_registered_wins(self):
        routes = [_route("GET", "posts/:slug"), _route("GET", "posts/:id<int>")]
        combined = combine(routes)
        assert combined.lookup("/posts/12", None) == (routes[0], {"slug": "12"})

    def test_same_placeholder_names_do_not_collide(self):
        routes = [_route("GET", "a/:id<int>"), _route("GET", "b/:id")]
        combined = combine(routes)
        assert combined.lookup("/a/1", None) == (routes[0], {"id": 1})
        assert combined.lookup("/b/x", None) == (routes[1], {"id": "x"})

    def test_several_placeholders_and_float(self):
        routes = [_route("GET", ":year<int>/:month<int>/:slug"), _route("GET", "n/:n<float>")]
        combined = combine(routes)
        assert combined.lookup("/2026/9/hello", None) == (
            routes[0],
            {"year": 2026, "month": 9, "slug": "hello"},
        )
        assert combined.lookup("/n/1.5", None) == (routes[1], {"n": 1.5})

    def test_regex_format_with_its_own_groups(self):
        # A format can carry unnamed groups; the placeholder is the param
        routes = [_route("GET", r"docs/:lang<(en|es)(-[A-Z]{2})?>")]
        combined = combine(routes)
        assert combined.lookup("/docs/es-AR", None) == (routes[0], {"lang": "es-AR"})
        assert combined.lookup("/docs/fr", None) is None
        assert routes[0].match("/docs/es-AR") == {"lang": "es-AR"}

    def test_no_placeholders(self):
        routes = [_route("GET", "a/:x"), Route("GET", "plain", host="h.com", redirect="/x")]
        # A hosted route is never combined, but a placeholder-less one could be
        combined = combine([routes[0], _route("GET", "static")])
        assert combined.lookup("/static", None) == (combined.routes[1], {})


class TestBucketed:
    def test_first_literal_segment(self):
        assert _first_literal_segment(_route("GET", "posts/:id")) == "posts"
        assert _first_literal_segment(_route("GET", "posts")) == "posts"
        assert _first_literal_segment(_route("GET", ":id/edit")) is None
        assert _first_literal_segment(_route("GET", "user-:name/x")) is None
        assert _first_literal_segment(_route("GET", ":file<path>")) is None

    def test_lookup_by_first_segment(self):
        a = _route("GET", "posts/:id<int>")
        b = _route("GET", "posts/:slug")
        c = _route("GET", "users/:name")
        bucketed = bucket([a, b, c])
        assert isinstance(bucketed, Bucketed)
        assert list(bucketed.buckets) == ["posts", "users"]
        assert bucketed.buckets["posts"].routes == (a, b)
        assert bucketed.lookup("/posts/1", None) == (a, {"id": 1})
        assert bucketed.lookup("/posts/x", None) == (b, {"slug": "x"})
        assert bucketed.lookup("/posts/x/", None) == (b, {"slug": "x"})
        assert bucketed.lookup("/users/ann", None) == (c, {"name": "ann"})
        assert bucketed.lookup("/users", None) is None
        assert bucketed.lookup("/nope/1", None) is None
        assert bucketed.lookup("/", None) is None


class TestHosted:
    def test_host_caster(self):
        route = _route("GET", "p", host=":port<int>.example.com")
        assert Hosted(route).lookup("/p", "8080.example.com") == (route, {"port": 8080})

    def test_host_then_path(self):
        route = _route("GET", "p/:id<int>", host=":sub.example.com")
        hosted = Hosted(route)
        assert hosted.lookup("/p/1", "www.example.com") == (route, {"sub": "www", "id": 1})
        assert hosted.lookup("/p/1", "other.com") is None
        assert hosted.lookup("/p/1", None) is None
        assert hosted.lookup("/q/1", "www.example.com") is None


class TestLowerRoutes:
    def _router(self, *routes):
        router = Router()
        for route in routes:
            router.add_route(route)
        return router

    def test_segments_keep_priority(self):
        a = _route("GET", "a/:x")
        b = _route("GET", "b/:x")
        h = _route("GET", "c/:x", host="h.com")
        c = _route("GET", "d/:x")
        any1 = _route("GET", ":x/one")
        any2 = _route("GET", ":x/two")
        d = _route("GET", "d/:y")
        p = _route("POST", "a/:x")
        router = self._router(a, b, h, c, any1, any2, d, p)
        table = lower_routes(router)
        assert isinstance(table, RouteTable)
        get = table.segments["GET"]
        assert [type(seg) for seg in get] == [Bucketed, Hosted, Bucketed, Combined, Bucketed]
        assert list(get[0].buckets) == ["a", "b"]
        assert get[1].route is h
        assert get[2].buckets["d"].routes == (c,)
        assert get[3].routes == (any1, any2)
        assert get[4].buckets["d"].routes == (d,)
        assert [type(seg) for seg in table.segments["POST"]] == [Bucketed]

    def test_placeholder_first_route_keeps_priority_over_a_later_literal(self):
        wild = _route("GET", ":x/foo")
        posts = _route("GET", "posts/:id")
        table = lower_routes(self._router(wild, posts))
        assert table.lookup("GET", "/posts/foo", None) == (wild, {"x": "posts"})
        assert table.lookup("GET", "/posts/7", None) == (posts, {"id": "7"})

    def test_static_and_build_only_routes_are_not_in_the_table(self):
        router = self._router(_route("GET", "static"), Route("GET", "b/:x", name="b"))
        assert lower_routes(router).segments == {}

    def test_lookup_and_allowed_methods(self):
        a = _route("GET", "a/:x")
        h = _route("GET", "h/:x", host="h.com")
        p = _route("POST", "a/:x")
        d = _route("DELETE", "h/:x", host="h.com")
        table = lower_routes(self._router(a, h, p, d))
        assert table.lookup("GET", "/a/1", None) == (a, {"x": "1"})
        assert table.lookup("GET", "/h/1", "h.com") == (h, {"x": "1"})
        assert table.lookup("GET", "/h/1", None) is None
        assert table.lookup("PUT", "/a/1", None) is None
        assert table.allowed_methods("PUT", "/a/1", None) == {"GET", "POST"}
        assert table.allowed_methods("GET", "/a/1", None) == {"POST"}
        assert table.allowed_methods("GET", "/h/1", "h.com") == {"DELETE"}
        assert table.allowed_methods("GET", "/h/1", None) == set()


class TestRouterUsesTheTable:
    def test_built_on_first_match_and_reset_by_add_route(self):
        router = Router()
        a = _route("GET", "a/:x")
        router.add_route(a)
        assert router._table is None
        assert router.match("GET", "/a/1") == (a, {"x": "1"})
        table = router._table
        assert table is not None
        assert router.match("GET", "/a/2")[1] == {"x": "2"}
        assert router._table is table

        b = _route("GET", "b/:x")
        router.add_route(b)
        assert router._table is None
        assert router.match("GET", "/b/1") == (b, {"x": "1"})

    def test_lower_builds_it_now(self):
        router = Router()
        router.add_route(_route("GET", "a/:x"))
        table = router.lower()
        assert router._table is table
        assert list(table.segments) == ["GET"]
        assert [type(seg) for seg in table.segments["GET"]] == [Bucketed]

    def test_defaults_are_merged(self):
        router = Router()
        route = Route("GET", "a/:x", redirect="/x", defaults={"k": "v", "x": "no"})
        router.add_route(route)
        assert router.match("GET", "/a/1") == (route, {"k": "v", "x": "1"})

    def test_405_and_404_through_the_table(self):
        router = Router()
        router.add_route(_route("GET", "a/:x"))
        router.add_route(_route("POST", "a/:x"))
        with pytest.raises(MethodNotAllowed) as exc:
            router.match("PUT", "/a/1")
        assert exc.value.headers["Allow"] == "GET, HEAD, POST"
        with pytest.raises(MatchNotFound):
            router.match("GET", "/zzz/1")

    def test_same_answers_as_matching_route_by_route(self):
        """The table must agree with `Route.match` tried in order."""
        router = Router()
        routes = [
            _route("GET", "posts"),
            _route("GET", "posts/:id<int>"),
            _route("GET", "posts/:slug"),
            _route("GET", "posts/:id<int>/comments/:cid<int>"),
            _route("GET", "users/:name", host=":sub.example.com"),
            _route("GET", "users/:name"),
            _route("GET", "files/:path<path>"),
            _route("GET", r"dates/:d<\d{4}-\d{2}>"),
            _route("GET", ":any/tail"),
            _route("GET", "posts/:id<int>/tail"),
        ]
        for route in routes:
            router.add_route(route)

        def slow(method, path, host):
            for route in routes:
                if route.method != method:
                    continue
                if not route.path_placeholders and not route.host:
                    if route.path == (path.rstrip("/") or "/"):
                        return route, {}
                    continue
                hp = route.match_host(host)
                if hp is None:
                    continue
                m = route.match(path)
                if m is not None:
                    return route, {**hp, **m}
            return None

        cases = [
            ("/posts", None), ("/posts/", None), ("/posts/7", None), ("/posts/x", None),
            ("/posts/7/comments/9", None), ("/posts/7/comments/x", None),
            ("/users/ann", None), ("/users/ann", "a.example.com"), ("/users/ann", "b.com"),
            ("/files/a/b/c", None), ("/dates/2026-09", None), ("/dates/26-9", None),
            ("/nope", None), ("/posts/tail", None), ("/posts/7/tail", None), ("/x/tail", None),
        ]
        for path, host in cases:
            expected = slow("GET", path, host)
            if expected is None:
                with pytest.raises(MatchNotFound):
                    router.match("GET", path, host)
            else:
                assert router.match("GET", path, host) == expected, (path, host)


class TestRouteFormatPrecompiled:
    def test_placeholder_regexes_and_templates(self):
        route = Route("GET", "posts/:id<int>", host=":sub.example.com", redirect="/x")
        assert isinstance(route._path_placeholder_re["id"], re.Pattern)
        assert route._path_template.substitute({"id": "1"}) == "/posts/1"
        assert route._host_template.substitute({"sub": "www"}) == "www.example.com"
        assert route.format(id=3, q="a") == "/posts/3?q=a"
        assert route.format_host(sub="www") == "www.example.com"

    def test_no_host(self):
        route = Route("GET", "posts", redirect="/x")
        assert route._host_template is None
        assert route._host_placeholder_re == {}
        assert route.format_host() is None

    def test_controller_prefix(self):
        route = Route("GET", "items/:item_id", to=ItemController.show)
        assert route.controller_prefix == "item_"
        assert route.controller_prefix == "item_"
        route.to = None
        assert route.controller_prefix == ""
