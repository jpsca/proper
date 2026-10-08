import importlib
import re
from urllib.parse import unquote

import pytest

from proper.errors import (
    BadRouteFormat,
    BadRoutePlaceholder,
    DuplicatedRoutePlaceholder,
    MissingRouteParameter,
)
from proper.router.route import (
    FORMATS,
    RE_PLACEHOLDERS,
    Route,
    StaticRoute,
)


# Module-level handler classes (qualname must be "Class.method" format)

class Handlers:
    def show(self): ...
    def index(self): ...
    def x(self): ...


class PageController:
    def show(self): ...
    def index(self): ...


class PhotoController:
    def index(self): ...


class Items:
    def list(self): ...



class TestREPlaceholders:
    def test_simple_placeholder(self):
        m = RE_PLACEHOLDERS.search("/photos/:id")
        assert m.group(1) == "id"
        assert m.group(2) is None

    def test_placeholder_with_format(self):
        m = RE_PLACEHOLDERS.search("/photos/:id<int>")
        assert m.group(1) == "id"
        assert m.group(2) == "int"

    def test_placeholder_with_custom_regex(self):
        m = RE_PLACEHOLDERS.search("/docs/:lang<en|es|pt>")
        assert m.group(1) == "lang"
        assert m.group(2) == "en|es|pt"

    def test_multiple_placeholders(self):
        matches = RE_PLACEHOLDERS.findall("/:year<int>/:month<int>/:slug")
        assert matches == [("year", "int"), ("month", "int"), ("slug", "")]

    def test_placeholder_with_underscores(self):
        m = RE_PLACEHOLDERS.search("/:photo_id")
        assert m.group(1) == "photo_id"

    def test_no_match_for_uppercase(self):
        m = RE_PLACEHOLDERS.search("/:ID")
        assert m is None

    def test_no_match_for_number_start(self):
        m = RE_PLACEHOLDERS.search("/:1name")
        assert m is None



class TestFormats:
    def test_default_format(self):
        assert None in FORMATS
        assert re.fullmatch(FORMATS[None], "hello")
        assert not re.fullmatch(FORMATS[None], "hello/world")

    def test_path_format(self):
        assert re.fullmatch(FORMATS["path"], "hello/world/foo")

    def test_int_format(self):
        assert re.fullmatch(FORMATS["int"], "42")
        assert not re.fullmatch(FORMATS["int"], "abc")
        assert not re.fullmatch(FORMATS["int"], "4.2")

    def test_float_format(self):
        assert re.fullmatch(FORMATS["float"], "3.14")
        assert not re.fullmatch(FORMATS["float"], "42")
        assert not re.fullmatch(FORMATS["float"], "abc")



class TestRouteInit:
    def test_method_uppercased(self):
        r = Route("get", "/")
        assert r.method == "GET"

    def test_method_setter_uppercases(self):
        r = Route("GET", "/")
        r.method = "post"
        assert r.method == "POST"

    def test_path_normalized_with_leading_slash(self):
        r = Route("GET", "photos")
        assert r.path == "/photos"

    def test_path_strips_trailing_slash(self):
        r = Route("GET", "/photos/")
        assert r.path == "/photos"

    def test_root_path(self):
        r = Route("GET", "/")
        assert r.path == "/"

    def test_empty_path_becomes_root(self):
        r = Route("GET", "")
        assert r.path == "/"

    def test_defaults_empty_dict_when_none(self):
        r = Route("GET", "/")
        assert r.defaults == {}

    def test_defaults_preserved(self):
        r = Route("GET", "/", defaults={"key": "val"})
        assert r.defaults == {"key": "val"}

    def test_host_stored(self):
        r = Route("GET", "/", host="example.com")
        assert r.host == "example.com"

    def test_redirect_stored(self):
        r = Route("GET", "/old", redirect="/new")
        assert r.redirect == "/new"

    def test_redirect_status_default(self):
        r = Route("GET", "/old", redirect="/new")
        assert r.redirect_status == 307



class TestRouteAutoNaming:
    def test_auto_name_from_handler(self):
        r = Route("GET", "/", to=PageController.show)
        assert r.name == "Page.show"

    def test_auto_name_strips_controller_suffix(self):
        r = Route("GET", "/", to=PhotoController.index)
        assert r.name == "Photo.index"

    def test_no_controller_suffix_kept(self):
        r = Route("GET", "/", to=Items.list)
        assert r.name == "Items.list"

    def test_explicit_name_not_overridden(self):
        r = Route("GET", "/", name="custom", to=PageController.show)
        assert r.name == "custom"

    def test_no_name_when_no_handler(self):
        r = Route("GET", "/")
        assert r.name is None



class TestBuildOnly:
    def test_build_only_when_no_to_no_redirect(self):
        r = Route("GET", "/foo")
        assert r.build_only is True

    def test_not_build_only_when_to_set(self):
        r = Route("GET", "/foo", to=Handlers.x)
        assert r.build_only is False

    def test_not_build_only_when_redirect_set(self):
        r = Route("GET", "/foo", redirect="/bar")
        assert r.build_only is False



class TestRouteRepr:
    def test_basic_repr(self):
        r = Route("GET", "/photos/:id", name="Photo.show", to=Handlers.show)
        s = repr(r)
        assert "GET" in s
        assert "/photos/:id" in s
        assert "Photo.show" in s

    def test_repr_with_host(self):
        r = Route("GET", "/", host="example.com")
        assert "host=" in repr(r)

    def test_repr_with_redirect(self):
        r = Route("GET", "/old", redirect="/new")
        assert "redirect=" in repr(r)



class TestRouteEquality:
    def test_equal_routes(self):
        r1 = Route("GET", "/foo", to=Handlers.x, name="test")
        r2 = Route("GET", "/foo", to=Handlers.x, name="test")
        assert r1 == r2

    def test_different_method(self):
        r1 = Route("GET", "/foo")
        r2 = Route("POST", "/foo")
        assert r1 != r2

    def test_different_path(self):
        r1 = Route("GET", "/foo")
        r2 = Route("GET", "/bar")
        assert r1 != r2

    def test_not_equal_to_non_route(self):
        r = Route("GET", "/foo")
        assert r != "not a route"



class TestRoutePathCompilation:
    def test_static_path_compiled(self):
        r = Route("GET", "/photos")
        assert r.path_re is not None
        assert r.path_placeholders == {}

    def test_single_placeholder(self):
        r = Route("GET", "/photos/:id")
        assert "id" in r.path_placeholders

    def test_placeholder_with_int_format(self):
        r = Route("GET", "/photos/:id<int>")
        assert r.path_placeholders["id"] == FORMATS["int"]

    def test_placeholder_with_float_format(self):
        r = Route("GET", "/items/:price<float>")
        assert r.path_placeholders["price"] == FORMATS["float"]

    def test_placeholder_with_path_format(self):
        r = Route("GET", "/files/:path<path>")
        assert r.path_placeholders["path"] == FORMATS["path"]

    def test_placeholder_with_custom_regex(self):
        r = Route("GET", "/docs/:lang<en|es|pt>")
        assert r.path_placeholders["lang"] == "en|es|pt"

    def test_multiple_placeholders(self):
        r = Route("GET", "/:year<int>/:month<int>/:day<int>/:slug")
        assert set(r.path_placeholders.keys()) == {"year", "month", "day", "slug"}

    def test_duplicate_placeholder_raises(self):
        with pytest.raises(DuplicatedRoutePlaceholder):
            Route("GET", "/:id/:id")

    def test_bad_regex_raises(self):
        with pytest.raises(BadRouteFormat):
            Route("GET", "/:name<[invalid>")

    def test_path_plain_stores_template(self):
        r = Route("GET", "/photos/:id")
        assert r.path_plain == "/photos/:id"

    def test_path_plain_with_format(self):
        r = Route("GET", "/photos/:id<int>")
        assert r.path_plain == "/photos/:id"



class TestRouteMatch:
    def test_match_static_path(self):
        r = Route("GET", "/photos")
        assert r.match("/photos") is not None

    def test_match_static_path_with_trailing_slash(self):
        r = Route("GET", "/photos")
        assert r.match("/photos/") is not None

    def test_no_match_different_path(self):
        r = Route("GET", "/photos")
        assert r.match("/videos") is None

    def test_match_placeholder(self):
        r = Route("GET", "/photos/:id")
        m = r.match("/photos/42")
        assert m is not None
        assert m["id"] == "42"

    def test_match_placeholder_any_string(self):
        r = Route("GET", "/photos/:id")
        m = r.match("/photos/hello-world")
        assert m is not None
        assert m["id"] == "hello-world"

    def test_placeholder_no_slash(self):
        r = Route("GET", "/photos/:id")
        assert r.match("/photos/hello/world") is None

    def test_match_int_format(self):
        r = Route("GET", "/photos/:id<int>")
        assert r.match("/photos/42") is not None
        assert r.match("/photos/abc") is None

    def test_match_float_format(self):
        r = Route("GET", "/items/:price<float>")
        assert r.match("/items/3.14") is not None
        assert r.match("/items/42") is None

    def test_match_path_format(self):
        r = Route("GET", "/files/:path<path>")
        m = r.match("/files/a/b/c.txt")
        assert m is not None
        assert m["path"] == "a/b/c.txt"

    def test_match_custom_regex(self):
        r = Route("GET", "/docs/:lang<en|es|pt>")
        assert r.match("/docs/en") is not None
        assert r.match("/docs/fr") is None

    def test_match_multiple_placeholders(self):
        r = Route("GET", "/:year<int>/:month<int>/:slug")
        m = r.match("/2024/01/hello-world")
        assert m is not None
        assert m["year"] == 2024
        assert m["month"] == 1
        assert m["slug"] == "hello-world"

    def test_match_root(self):
        r = Route("GET", "/")
        assert r.match("/") is not None

    def test_no_partial_match(self):
        r = Route("GET", "/photos")
        assert r.match("/photos/42") is None

    def test_match_complex_regex(self):
        r = Route("GET", "/:year<\\d{4}>/:month<\\d{2}>")
        m = r.match("/2024/01")
        assert m is not None
        assert m["year"] == "2024"
        assert r.match("/24/1") is None

    def test_match_literal_special_chars_in_path(self):
        r = Route("GET", "/api/v1.0/items")
        assert r.match("/api/v1.0/items") is not None
        # The dot should be escaped in the regex
        assert r.match("/api/v1X0/items") is None

    @pytest.mark.parametrize(
        "path, url",
        [
            ("/files/:name", "/files/."),
            ("/files/:name", "/files/.."),
            ("/files/:name", "/files/../"),
            ("/files/:name/edit", "/files/../edit"),
            ("/docs/:page<path>", "/docs/a/../b"),
            ("/docs/:page<path>", "/docs/a/."),
            ("/docs/:page<path>", "/docs/../a"),
            ("/x/:a:b", "/x/.."),
            ("/x/.:a", "/x/.."),
        ],
    )
    def test_no_match_when_a_value_is_a_dot_segment(self, path, url):
        """`format` can't build a URL with such a value, because clients
        remove `.` and `..` segments, so the route doesn't match it."""
        r = Route("GET", path)
        assert r.match(url) is None

    @pytest.mark.parametrize(
        "path, url, expected",
        [
            ("/files/:name", "/files/...", {"name": "..."}),
            ("/files/:name", "/files/.env", {"name": ".env"}),
            ("/files/:name", "/files/a..", {"name": "a.."}),
            ("/docs/:page<path>", "/docs/a/.b/c", {"page": "a/.b/c"}),
            # The dot segment is the route's own text.
            ("/a/../:name", "/a/../b", {"name": "b"}),
            ("/:year<int>/./:slug", "/2024/./x", {"year": 2024, "slug": "x"}),
        ],
    )
    def test_match_dots_that_are_not_a_value_dot_segment(self, path, url, expected):
        r = Route("GET", path)
        assert r.match(url) == expected


class TestRouteFormat:
    def test_format_static_path(self):
        r = Route("GET", "/photos")
        assert r.format() == "/photos"

    def test_format_with_placeholder(self):
        r = Route("GET", "/photos/:id")
        assert r.format(id="42") == "/photos/42"

    def test_format_multiple_placeholders(self):
        r = Route("GET", "/:year/:month/:slug")
        url = r.format(year="2024", month="01", slug="hello")
        assert url == "/2024/01/hello"

    def test_format_missing_param_raises(self):
        r = Route("GET", "/photos/:id")
        with pytest.raises(MissingRouteParameter):
            r.format()

    def test_format_bad_placeholder_raises(self):
        r = Route("GET", "/photos/:id<int>")
        with pytest.raises(BadRoutePlaceholder):
            r.format(id="abc")

    def test_format_extra_params_become_query_string(self):
        r = Route("GET", "/photos/:id")
        url = r.format(id="42", page="2", sort="name")
        assert url.startswith("/photos/42?")
        assert "page=2" in url
        assert "sort=name" in url

    def test_format_no_extra_params_no_query_string(self):
        r = Route("GET", "/photos/:id")
        url = r.format(id="42")
        assert "?" not in url

    def test_format_int_param_converted_to_string(self):
        r = Route("GET", "/photos/:id<int>")
        url = r.format(id=42)
        assert url == "/photos/42"

    def test_format_root_path(self):
        r = Route("GET", "/")
        assert r.format() == "/"

    def test_format_validates_custom_regex(self):
        r = Route("GET", "/docs/:lang<en|es|pt>")
        assert r.format(lang="en") == "/docs/en"
        with pytest.raises(BadRoutePlaceholder):
            r.format(lang="fr")

    @pytest.mark.parametrize(
        "path, value",
        [
            ("/photos/:value<int>", "42abc"),
            ("/photos/:value<float>", "1.5x"),
            ("/docs/:value<en|es|pt>", "english"),
            ("/docs/:value<en|es|pt>", "xen"),
            ("/photos/:value", "a/b"),
        ],
    )
    def test_format_validates_the_whole_value(self, path, value):
        r = Route("GET", path)
        with pytest.raises(BadRoutePlaceholder):
            r.format(value=value)

    def test_format_percent_encodes_path_values(self):
        r = Route("GET", "/tags/:tag")
        assert r.format(tag="a b?c#d%e") == "/tags/a%20b%3Fc%23d%25e"
        assert r.format(tag="café") == "/tags/caf%C3%A9"

    def test_format_percent_encodes_the_text_of_the_route(self):
        """A route is matched against the decoded path, so its text is
        encoded as the values are."""
        r = Route("GET", "/über/my files/:id")
        url = r.format(id="a b")
        assert url == "/%C3%BCber/my%20files/a%20b"
        assert r.match(unquote(url)) == {"id": "a b"}

    def test_format_percent_encodes_a_query_value_that_is_not_a_string(self):
        r = Route("GET", "/search")
        assert r.format(c=[1, 2], n=3) == "/search?c=%5B1%2C+2%5D&n=3"

    def test_format_keeps_slashes_in_path_values(self):
        r = Route("GET", "/docs/:page<path>")
        assert r.format(page="guide/intro to proper") == "/docs/guide/intro%20to%20proper"

    def test_format_keeps_the_characters_a_path_allows(self):
        r = Route("GET", "/files/:name")
        assert r.format(name="a:b@c!$&'()*+,;=d") == "/files/a:b@c!$&'()*+,;=d"
        assert r.format(name="a b?c#d%e") == "/files/a%20b%3Fc%23d%25e"

    def test_format_keeps_a_placeholder_like_value(self):
        # A client-side URL template, as the rich-text editor builds for Lexxy.
        r = Route("GET", "/storage/redirect/:token/:filename")
        url = r.format(token=":signed_id", filename=":filename")
        assert url == "/storage/redirect/:signed_id/:filename"

    def test_format_percent_encodes_the_query_string(self):
        r = Route("GET", "/search")
        url = r.format(**{"q": "a b&c=d", "sort by": "date/desc", "tag": "café"})
        assert url == "/search?q=a+b%26c%3Dd&sort+by=date%2Fdesc&tag=caf%C3%A9"

    def test_format_uppercase_colon_text_is_literal(self):
        r = Route("GET", "/items/:ID/:id")
        assert r.path_placeholders == {"id": r"[^\/]+"}
        assert r.format(id="7") == "/items/:ID/7"

    def test_format_colon_not_followed_by_a_name_is_literal(self):
        r = Route("GET", "/time/10:30/:x:")
        assert r.format(x="y") == "/time/10:30/y:"

    def test_format_double_colon_as_in_matching(self):
        r = Route("GET", "/a::b")
        assert r.match("/a:x") == {"b": "x"}
        assert r.format(b="x") == "/a:x"

    def test_format_placeholder_with_format_followed_by_letters(self):
        r = Route("GET", "/:a<int>bc")
        assert r.match("/1bc") == {"a": 1}
        assert r.format(a=1) == "/1bc"

    @pytest.mark.parametrize(
        "path, values, name",
        [
            ("/files/:name", {"name": "."}, "name"),
            ("/files/:name", {"name": ".."}, "name"),
            ("/files/:name/edit", {"name": ".."}, "name"),
            ("/:name", {"name": "."}, "name"),
            ("/docs/:page<path>", {"page": "a/../b"}, "page"),
            ("/docs/:page<path>", {"page": "a/."}, "page"),
            ("/docs/:page<path>", {"page": "../a"}, "page"),
            # Two values that make one `..` segment together.
            ("/x/:a:b", {"a": ".", "b": "."}, "a"),
            # The value is next to the text of the route.
            ("/x/.:a", {"a": "."}, "a"),
        ],
    )
    def test_format_rejects_a_dot_segment(self, path, values, name):
        """Clients remove `.` and `..` segments (RFC 3986 §5.2.4), so the
        URL would not lead to the route."""
        r = Route("GET", path)
        with pytest.raises(BadRoutePlaceholder, match=f"placeholder {name} would make"):
            r.format(**values)

    @pytest.mark.parametrize(
        "path, values, expected",
        [
            ("/files/:name", {"name": "..."}, "/files/..."),
            ("/files/:name", {"name": ".x"}, "/files/.x"),
            ("/files/:name", {"name": "a.."}, "/files/a.."),
            ("/files/x:name", {"name": "."}, "/files/x."),
            ("/files/:name.json", {"name": "."}, "/files/..json"),
            ("/docs/:page<path>", {"page": "a/.b/c"}, "/docs/a/.b/c"),
            # Percent-encoded dots stay encoded: `%2e` is `%252e`.
            ("/files/:name", {"name": "%2e%2e"}, "/files/%252e%252e"),
            ("/files/:name", {"name": "a"}, "/files/a"),
        ],
    )
    def test_format_accepts_dots_that_are_not_a_dot_segment(self, path, values, expected):
        r = Route("GET", path)
        assert r.format(**values) == expected

    def test_format_dot_segments_in_the_route_text_are_its_own(self):
        r = Route("GET", "/a/../:name")
        assert r.format(name="b") == "/a/../b"
        assert r.format(name="...") == "/a/../..."



class TestRoutePathReassignment:
    def test_path_setter_recompiles(self):
        r = Route("GET", "/photos")
        old_re = r.path_re
        r.path = "/videos/:id"
        assert r.path == "/videos/:id"
        assert r.path_re != old_re
        assert "id" in r.path_placeholders



class TestStaticRoute:
    def test_static_route_is_get(self):
        r = StaticRoute("/static", root="/tmp/static")
        assert r.method == "GET"

    def test_static_route_path(self):
        r = StaticRoute("/static", root="/tmp/static")
        assert r.path == "/static/:file<path>"

    def test_static_route_path_format_is_path(self):
        r = StaticRoute("/static", root="/tmp/static")
        assert r.path_placeholders["file"] == FORMATS["path"]

    def test_static_route_stores_root_in_defaults(self):
        r = StaticRoute("/static", root="/tmp/static")
        assert r.defaults["root"] == "/tmp/static"

    def test_static_route_stores_url_in_defaults(self):
        r = StaticRoute("/assets", root="/tmp/assets")
        assert r.defaults["url"] == "/assets"

    def test_static_route_public_default(self):
        r = StaticRoute("/static", root="/tmp/static")
        assert r.defaults["public"] is True

    def test_static_route_fingerprint_default(self):
        r = StaticRoute("/static", root="/tmp/static")
        assert r.defaults["fp"] is True

    def test_static_route_format_without_fingerprint(self):
        r = StaticRoute("/static", root="/tmp/static", fingerprint=False)
        url = r.format(file="style.css")
        assert url == "/static/style.css"

    def test_static_route_format_fingerprint_missing_file(self, tmp_path):
        r = StaticRoute("/static", root=str(tmp_path), fingerprint=True)
        url = r.format(file="nonexistent.css")
        assert url == "/static/nonexistent.css"

    def test_static_route_format_fingerprint_existing_file(self, tmp_path):
        css = tmp_path / "style.css"
        css.write_text("body { color: red; }")
        r = StaticRoute("/static", root=str(tmp_path), fingerprint=True)
        url = r.format(file="style.css")
        assert url.startswith("/static/style-")
        assert url.endswith(".css")
        assert len(url) > len("/static/style.css")

    def test_static_route_format_fingerprint_nested_file(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        css = subdir / "style.css"
        css.write_text("body {}")
        r = StaticRoute("/static", root=str(tmp_path), fingerprint=True)
        url = r.format(file="sub/style.css")
        assert "sub/style-" in url
        assert url.endswith(".css")

    def test_static_route_format_fingerprint_changes_on_content(self, tmp_path):
        css = tmp_path / "style.css"
        css.write_text("v1")
        r = StaticRoute("/static", root=str(tmp_path), fingerprint=True)
        url1 = r.format(file="style.css")
        css.write_text("v2")
        url2 = r.format(file="style.css")

        assert url1 != url2

    def test_static_route_format_missing_file_param_raises(self):
        r = StaticRoute("/static", root="/tmp/static", fingerprint=True)
        with pytest.raises(MissingRouteParameter):
            r.format()

    def test_static_route_custom_name(self):
        r = StaticRoute("/static", root="/tmp", name="assets")
        assert r.name == "assets"

    def test_static_route_allowed_ext(self):
        r = StaticRoute("/static", root="/tmp", allowed_ext=[".css", ".js"])
        assert r.defaults["allowed_ext"] == [".css", ".js"]

    def test_static_route_host(self):
        r = StaticRoute("/static", root="/tmp", host="cdn.example.com")
        assert r.host == "cdn.example.com"



class TestHostCompilation:
    def test_no_host_compiles_to_none(self):
        r = Route("GET", "/")
        assert r.host_re is None
        assert r.host_plain is None
        assert r.host_placeholders == {}

    def test_literal_host_compiles_without_placeholders(self):
        r = Route("GET", "/", host="api.example.com")
        assert r.host_re is not None
        assert r.host_plain == "api.example.com"
        assert r.host_placeholders == {}

    def test_placeholder_host_extracts_names(self):
        r = Route("GET", "/", host=":lang<en|es|pt>.example.com")
        assert "lang" in r.host_placeholders
        assert r.host_placeholders["lang"] == "en|es|pt"

    def test_placeholder_host_compiles_regex(self):
        r = Route("GET", "/", host=":username.myapp.com")
        assert r.host_re.match("alice.myapp.com")
        assert r.host_re.match("bob.myapp.com")
        assert not r.host_re.match("alice.other.com")

    def test_host_setter_recompiles(self):
        r = Route("GET", "/")
        r.host = ":sub.example.com"
        assert "sub" in r.host_placeholders
        r.host = None
        assert r.host_re is None

    def test_duplicated_host_placeholder_raises(self):
        with pytest.raises(DuplicatedRoutePlaceholder):
            Route("GET", "/", host=":x.:x.example.com")

    def test_bad_host_format_raises(self):
        with pytest.raises(BadRouteFormat):
            Route("GET", "/", host=":x<(unclosed>.example.com")


class TestRouteMatchHost:
    def test_no_constraint_returns_empty_dict(self):
        r = Route("GET", "/")
        assert r.match_host("anything.example.com") == {}
        assert r.match_host(None) == {}

    def test_literal_host_matches(self):
        r = Route("GET", "/", host="api.example.com")
        assert r.match_host("api.example.com") == {}

    def test_literal_host_mismatch(self):
        r = Route("GET", "/", host="api.example.com")
        assert r.match_host("www.example.com") is None

    def test_placeholder_host_captures_value(self):
        r = Route("GET", "/", host=":lang<en|es|pt>.example.com")
        assert r.match_host("es.example.com") == {"lang": "es"}

    def test_placeholder_host_rejects_non_matching(self):
        r = Route("GET", "/", host=":lang<en|es|pt>.example.com")
        assert r.match_host("de.example.com") is None

    def test_placeholder_host_wildcard_subdomain(self):
        r = Route("GET", "/", host=":username.myapp.com")
        assert r.match_host("alice.myapp.com") == {"username": "alice"}

    def test_none_host_against_constraint(self):
        r = Route("GET", "/", host="api.example.com")
        assert r.match_host(None) is None

    def test_host_anchor_is_strict(self):
        # Should not match a suffix
        r = Route("GET", "/", host=":lang<en|es>.example.com")
        assert r.match_host("es.example.com.evil.com") is None


class TestRouteFormatHost:
    def test_no_constraint_returns_none(self):
        r = Route("GET", "/")
        assert r.format_host() is None

    def test_literal_host_returns_as_is(self):
        r = Route("GET", "/", host="api.example.com")
        assert r.format_host() == "api.example.com"

    def test_placeholder_host_substitutes(self):
        r = Route("GET", "/", host=":lang<en|es|pt>.example.com")
        assert r.format_host(lang="es") == "es.example.com"

    def test_placeholder_host_missing_param_raises(self):
        r = Route("GET", "/", host=":lang.example.com")
        with pytest.raises(MissingRouteParameter):
            r.format_host()

    def test_placeholder_host_bad_value_raises(self):
        r = Route("GET", "/", host=":lang<en|es|pt>.example.com")
        with pytest.raises(BadRoutePlaceholder):
            r.format_host(lang="de")

    def test_placeholder_host_validates_the_whole_value(self):
        r = Route("GET", "/", host=":lang<en|es|pt>.example.com")
        with pytest.raises(BadRoutePlaceholder):
            r.format_host(lang="english")

    def test_host_with_a_port_formats_as_is(self):
        r = Route("GET", "/", host="localhost:5000")
        assert r.format_host() == "localhost:5000"

    def test_host_uppercase_colon_text_is_literal(self):
        r = Route("GET", "/", host="localhost:PORT")
        assert r.host_placeholders == {}
        assert r.format_host() == "localhost:PORT"

    @pytest.mark.parametrize(
        "value",
        [
            "evil.com?",
            "evil.com#",
            "u@evil.com",
            "evil.com:80",
            "a b",
            "a\r\nSet-Cookie: s=1",
            "a\n",
            "a\t",
            "%41",
            "[::1]",
            "a\\b",
            "a!b",
            "a$b",
            "a&b",
            "a'b",
            "a(b",
            "a*b",
            "a+b",
            "a,b",
            "a;b",
            "a=b",
            "jos\u00e9",
            "a\x00",
        ],
    )
    def test_placeholder_host_refuses_a_character_a_host_name_cannot_have(
        self, value
    ):
        # The default format `[^/]+` accepts all of these, and the value
        # becomes the host of the URL as it is.
        r = Route("GET", "/h/1", host=":sub.example.com")
        assert re.fullmatch(FORMATS[None], value)
        with pytest.raises(BadRoutePlaceholder, match="host name"):
            r.format_host(sub=value)

    @pytest.mark.parametrize(
        "value", ["alice", "Alice-2", "a.b", "a_b", "a~b", "0", "xn--jos-dma"]
    )
    def test_placeholder_host_accepts_host_name_characters(self, value):
        r = Route("GET", "/h/1", host=":sub.example.com")
        assert r.format_host(sub=value) == f"{value}.example.com"

    def test_placeholder_host_custom_format_is_checked_too(self):
        # A format that accepts the character doesn't make it valid in a host.
        r = Route("GET", "/", host=":sub<.+>.example.com")
        with pytest.raises(BadRoutePlaceholder, match="host name"):
            r.format_host(sub="a?b")


class TestRouteTemplateIsRemoved:
    """The CHANGELOG says `RouteTemplate` is removed and importing it raises
    `ImportError`. Before, both `proper.router` and `proper.router.route`
    exported it."""

    def test_importing_it_raises_import_error(self):
        with pytest.raises(ImportError, match="RouteTemplate"):
            from proper.router import RouteTemplate  # noqa: F401, PLC0415
        with pytest.raises(ImportError, match="RouteTemplate"):
            from proper.router.route import RouteTemplate  # noqa: F401, PLC0415

    @pytest.mark.parametrize("module", ["proper.router", "proper.router.route"])
    def test_it_is_not_an_attribute(self, module):
        mod = importlib.import_module(module)
        with pytest.raises(AttributeError):
            mod.RouteTemplate  # noqa: B018
        assert "RouteTemplate" not in mod.__all__
