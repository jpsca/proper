import pytest

from proper.channels import Channel
from proper.errors import MatchNotFound, MethodNotAllowed, RouteNotFound
from proper.global_context import current
from proper.router.route import Route, _namespace_prefix
from proper.router.router import (
    GROUP_ROUTES,
    SINGLE_ROUTES,
    BaseRouter,
    Router,
    ScopedRouter,
)


class Handlers:
    """Generic handlers for testing. qualname = 'Handlers.method'."""
    def action(self): ...
    def index(self): ...
    def show(self): ...
    def create(self): ...
    def update(self): ...
    def destroy(self): ...
    def search(self): ...
    def opts(self): ...


class PageController:
    def index(self): ...
    def show(self): ...
    def new(self): ...
    def create(self): ...
    def edit(self): ...
    def update(self): ...
    def delete(self): ...


class PhotoController:
    def index(self): ...
    def show(self): ...
    def new(self): ...
    def create(self): ...
    def edit(self): ...
    def update(self): ...
    def delete(self): ...


class ProfileController:
    def show(self): ...
    def new(self): ...
    def create(self): ...
    def edit(self): ...
    def update(self): ...
    def delete(self): ...


class PartialItemController:
    """Only has index and show."""
    def index(self): ...
    def show(self): ...


class ItemController:
    def show(self): ...


class PostController:
    def show(self): ...


class TestAddRoute:
    def test_add_route(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert r in router.routes

    def test_add_route_indexed_by_name(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router._routes_by_name["photos"] is r

    def test_add_route_without_name(self):
        router = BaseRouter()
        r = Route("GET", "/photos")
        router.add_route(r)
        assert r in router.routes

    def test_first_route_with_name_wins(self):
        router = BaseRouter()
        r1 = Route("GET", "/a", name="test", to=Handlers.action)
        r2 = Route("GET", "/b", name="test", to=Handlers.action)
        router.add_route(r1)
        router.add_route(r2)
        assert router._routes_by_name["test"] is r1

    def test_multiple_routes(self):
        router = BaseRouter()
        r1 = Route("GET", "/a", to=Handlers.action)
        r2 = Route("POST", "/b", to=Handlers.create)
        router.add_route(r1)
        router.add_route(r2)
        assert len(router.routes) == 2


class TestMatch:
    def test_match_simple_route(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        matched, params = router.match("GET", "/photos")
        assert matched is r
        assert params == {}

    def test_match_with_params(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id", name="photo", to=Handlers.action)
        router.add_route(r)
        matched, params = router.match("GET", "/photos/42")
        assert matched is r
        assert params == {"id": "42"}

    def test_match_with_defaults(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id", to=Handlers.action, defaults={"format": "html"})
        router.add_route(r)
        matched, params = router.match("GET", "/photos/42")
        assert params["id"] == "42"
        assert params["format"] == "html"

    def test_match_defaults_overridden_by_path(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id", to=Handlers.action, defaults={"id": "default"})
        router.add_route(r)
        _, params = router.match("GET", "/photos/42")
        assert params["id"] == "42"

    def test_match_trailing_slash(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)
        matched, _ = router.match("GET", "/photos/")
        assert matched is r

    def test_match_first_route_wins(self):
        router = BaseRouter()
        r1 = Route("GET", "/photos/:id", name="first", to=Handlers.action)
        r2 = Route("GET", "/photos/:slug", name="second", to=Handlers.show)
        router.add_route(r1)
        router.add_route(r2)
        matched, _ = router.match("GET", "/photos/42")
        assert matched is r1

    def test_match_not_found_raises(self):
        router = BaseRouter()
        with pytest.raises(MatchNotFound):
            router.match("GET", "/nonexistent")

    def test_method_not_allowed_raises(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)
        with pytest.raises(MethodNotAllowed) as exc_info:
            router.match("POST", "/photos")
        assert "GET" in str(exc_info.value.headers.get("Allow", ""))

    def test_method_not_allowed_collects_all_methods(self):
        router = BaseRouter()
        router.add_route(Route("GET", "/photos", name="a", to=Handlers.action))
        router.add_route(Route("POST", "/photos", name="b", to=Handlers.create))
        router.add_route(Route("DELETE", "/photos", name="c", to=Handlers.destroy))
        with pytest.raises(MethodNotAllowed) as exc_info:
            router.match("PATCH", "/photos")
        allow = exc_info.value.headers["Allow"]
        assert "GET" in allow
        assert "POST" in allow
        assert "DELETE" in allow

    def test_match_skips_build_only_routes(self):
        router = BaseRouter()
        r_build = Route("GET", "/photos/:id", name="build")
        r_real = Route("GET", "/photos/:id", name="real", to=Handlers.action)
        router.add_route(r_build)
        router.add_route(r_real)
        matched, _ = router.match("GET", "/photos/42")
        assert matched is r_real

    def test_match_with_redirect_route(self):
        router = BaseRouter()
        r = Route("GET", "/old", redirect="/new")
        router.add_route(r)
        matched, _ = router.match("GET", "/old")
        assert matched is r
        assert matched.redirect == "/new"

    def test_match_with_host(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action, host="api.example.com")
        router.add_route(r)
        matched, _ = router.match("GET", "/photos", host="api.example.com")
        assert matched is r

    def test_match_host_mismatch(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action, host="api.example.com")
        router.add_route(r)
        with pytest.raises(MatchNotFound):
            router.match("GET", "/photos", host="www.example.com")

    def test_match_host_none_matches_route_without_host(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)
        matched, _ = router.match("GET", "/photos", host=None)
        assert matched is r

    def test_match_host_none_skips_route_with_host(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action, host="api.example.com")
        router.add_route(r)
        with pytest.raises(MatchNotFound):
            router.match("GET", "/photos", host=None)

    def test_match_routes_with_different_hosts(self):
        router = BaseRouter()
        r_api = Route("GET", "/data", name="api", to=Handlers.action, host="api.example.com")
        r_web = Route("GET", "/data", name="web", to=Handlers.show, host="www.example.com")
        router.add_route(r_api)
        router.add_route(r_web)

        matched, _ = router.match("GET", "/data", host="api.example.com")
        assert matched is r_api

        matched, _ = router.match("GET", "/data", host="www.example.com")
        assert matched is r_web

    def test_match_placeholder_host_extracts_param(self):
        router = BaseRouter()
        r = Route("GET", "/docs", to=Handlers.action, host=":lang<en|es|pt>.example.com")
        router.add_route(r)
        matched, params = router.match("GET", "/docs", host="es.example.com")
        assert matched is r
        assert params["lang"] == "es"

    def test_match_placeholder_host_rejects_non_matching(self):
        router = BaseRouter()
        r = Route("GET", "/docs", to=Handlers.action, host=":lang<en|es|pt>.example.com")
        router.add_route(r)
        with pytest.raises(MatchNotFound):
            router.match("GET", "/docs", host="de.example.com")

    def test_match_wildcard_subdomain(self):
        router = BaseRouter()
        r = Route("GET", "/", to=Handlers.show, host=":username.myapp.com")
        router.add_route(r)
        matched, params = router.match("GET", "/", host="alice.myapp.com")
        assert matched is r
        assert params["username"] == "alice"

    def test_match_host_and_path_placeholders_combined(self):
        router = BaseRouter()
        r = Route("GET", "/users/:id<int>", to=Handlers.show, host=":tenant.example.com")
        router.add_route(r)
        matched, params = router.match("GET", "/users/42", host="acme.example.com")
        assert matched is r
        assert params["tenant"] == "acme"
        assert params["id"] == 42

    def test_match_placeholder_host_405_detection(self):
        router = BaseRouter()
        r = Route("GET", "/docs", to=Handlers.action, host=":lang<en|es>.example.com")
        router.add_route(r)
        with pytest.raises(MethodNotAllowed) as exc:
            router.match("POST", "/docs", host="en.example.com")
        assert "GET" in exc.value.headers["Allow"]

    def test_match_int_format_param(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id<int>", to=Handlers.action)
        router.add_route(r)
        matched, params = router.match("GET", "/photos/42")
        assert params["id"] == 42

    def test_match_float_format_param(self):
        router = BaseRouter()
        r = Route("GET", "/celsius/:temp<float>", to=Handlers.action)
        router.add_route(r)
        matched, params = router.match("GET", "/celsius/36.6")
        assert params["temp"] == 36.6

    def test_match_int_format_rejects_non_int(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id<int>", to=Handlers.action)
        router.add_route(r)
        with pytest.raises(MatchNotFound):
            router.match("GET", "/photos/abc")

    def test_match_path_format_param(self):
        router = BaseRouter()
        r = Route("GET", "/files/:filepath<path>", to=Handlers.action)
        router.add_route(r)
        matched, params = router.match("GET", "/files/a/b/c.txt")
        assert params["filepath"] == "a/b/c.txt"

    def test_match_root_path(self):
        router = BaseRouter()
        r = Route("GET", "/", to=Handlers.action)
        router.add_route(r)
        matched, _ = router.match("GET", "/")
        assert matched is r

    def test_match_method_case_matters(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)
        # lowercase method should not match uppercase
        with pytest.raises(MethodNotAllowed):
            router.match("get", "/photos")


class TestUrlFor:
    def test_url_for_simple(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_for("photos") == "/photos"

    def test_url_for_with_param(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id", name="photo", to=Handlers.action)
        router.add_route(r)
        assert router.url_for("photo", id="42") == "/photos/42"

    def test_url_for_with_query_params(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        url = router.url_for("photos", page="2")
        assert url == "/photos?page=2"

    def test_url_for_missing_route_raises(self):
        router = BaseRouter()
        with pytest.raises(RouteNotFound):
            router.url_for("nonexistent")

    def test_url_for_absolute_path_passthrough(self):
        router = BaseRouter()
        assert router.url_for("/some/absolute/path") == "/some/absolute/path"

    def test_url_for_strips_controller_suffix_from_name(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="Photo.index", to=Handlers.action)
        router.add_route(r)
        assert router.url_for("Photo.index") == "/photos"

    def test_url_for_with_anchor(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        url = router.url_for("photos", _anchor="top")
        assert url == "/photos#top"

    def test_url_for_with_param_and_anchor(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id", name="photo", to=Handlers.action)
        router.add_route(r)
        url = router.url_for("photo", id="42", _anchor="comments")
        assert url == "/photos/42#comments"

    def test_url_for_with_object(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:photo_id", to=PhotoController.show)
        router.add_route(r)

        class Photo:
            photo_id = 42

        url = router.url_for("Photo.show", Photo())
        assert url == "/photos/42"

    def test_url_for_with_object_strips_prefix(self):
        router = BaseRouter()
        r = Route("GET", "/items/:item_id", to=ItemController.show)
        router.add_route(r)

        class Item:
            id = 99

        url = router.url_for("Item.show", Item())
        assert url == "/items/99"

    def test_url_for_with_object_explicit_kwarg_takes_priority(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:photo_id", to=PhotoController.show)
        router.add_route(r)

        class Photo:
            photo_id = 42

        url = router.url_for("Photo.show", Photo(), photo_id=99)
        assert url == "/photos/99"

    def test_url_for_build_only_route(self):
        router = BaseRouter()
        r = Route("GET", "/external/:id", name="external")
        router.add_route(r)
        assert router.url_for("external", id="42") == "/external/42"

    def test_url_for_strips_host_placeholder_from_query_string(self):
        # `lang` is a host placeholder; it must NOT leak into the path's query string.
        router = BaseRouter()
        r = Route("GET", "/docs", name="docs", to=Handlers.action,
                  host=":lang<en|es|pt>.example.com")
        router.add_route(r)
        assert router.url_for("docs", lang="es") == "/docs"

    def test_url_for_full_with_placeholder_host(self, app):
        router = app.router
        r = Route("GET", "/docs", name="docs", to=Handlers.action,
                  host=":lang<en|es|pt>.example.com")
        router.add_route(r)
        url = router.url_for("docs", lang="pt", _full=True)
        assert url.endswith("://pt.example.com/docs")

    def test_url_for_full_with_literal_host_uses_route_host(self, app):
        router = app.router
        r = Route("GET", "/api", name="api", to=Handlers.action,
                  host="api.example.com")
        router.add_route(r)
        url = router.url_for("api", _full=True)
        assert url.endswith("://api.example.com/api")

    def test_url_for_with_object_fills_host_placeholder(self):
        router = BaseRouter()
        r = Route("GET", "/", to=ProfileController.show, host=":username.myapp.com")
        router.add_route(r)

        class User:
            username = "alice"

        # url_for without _full just builds the path - but the host placeholder
        # value should still be consumed and not bleed into a query string.
        url = router.url_for("Profile.show", User())
        assert url == "/"


class TestUrlIs:
    def test_url_is_matches(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_is("photos", curr_url="/photos") is True

    def test_url_is_matches_trailing_slash(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_is("photos", curr_url="/photos/") is True

    def test_url_is_no_match(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_is("photos", curr_url="/videos") is False



class TestUrlStartsWith:
    def test_exact_match(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_startswith("photos", curr_url="/photos") is True

    def test_prefix_match(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_startswith("photos", curr_url="/photos/42") is True

    def test_no_partial_word_match(self):
        router = BaseRouter()
        r = Route("GET", "/photo", name="photo", to=Handlers.action)
        router.add_route(r)
        assert router.url_startswith("photo", curr_url="/photography") is False

    def test_trailing_slash_in_curr_url(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_startswith("photos", curr_url="/photos/") is True

    def test_no_match(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)
        assert router.url_startswith("photos", curr_url="/videos") is False



class TestHTTPMethodDecorators:
    def test_get_decorator(self):
        router = BaseRouter()
        router.get("/photos")(Handlers.index)
        assert len(router.routes) == 1
        assert router.routes[0].method == "GET"
        assert router.routes[0].path == "/photos"

    def test_post_decorator(self):
        router = BaseRouter()
        router.post("/photos")(Handlers.create)
        assert router.routes[0].method == "POST"

    def test_put_decorator(self):
        router = BaseRouter()
        router.put("/photos/:id")(Handlers.update)
        assert router.routes[0].method == "PUT"

    def test_delete_decorator(self):
        router = BaseRouter()
        router.delete("/photos/:id")(Handlers.destroy)
        assert router.routes[0].method == "DELETE"

    def test_patch_decorator(self):
        router = BaseRouter()
        router.patch("/photos/:id")(Handlers.update)
        assert router.routes[0].method == "PATCH"

    def test_options_decorator(self):
        router = BaseRouter()
        router.options("/photos")(Handlers.opts)
        assert router.routes[0].method == "OPTIONS"

    def test_query_decorator(self):
        router = BaseRouter()
        router.query("/search")(Handlers.search)
        assert router.routes[0].method == "QUERY"

    def test_decorator_returns_original_function(self):
        router = BaseRouter()
        result = router.get("/photos")(Handlers.index)
        assert result is Handlers.index

    def test_decorator_with_name(self):
        router = BaseRouter()
        router.get("/photos", name="photo_list")(Handlers.index)
        assert router.routes[0].name == "photo_list"

    def test_decorator_with_host(self):
        router = BaseRouter()
        router.get("/api", host="api.example.com")(Handlers.index)
        assert router.routes[0].host == "api.example.com"

    def test_decorator_with_defaults(self):
        router = BaseRouter()
        router.get("/photos", defaults={"format": "json"})(Handlers.index)
        assert router.routes[0].defaults == {"format": "json"}

    def test_get_with_redirect(self):
        router = BaseRouter()
        router.get("/old", redirect="/new")
        assert len(router.routes) == 1
        assert router.routes[0].redirect == "/new"

    def test_options_with_redirect(self):
        router = BaseRouter()
        router.options("/old", redirect="/new")
        assert router.routes[0].redirect == "/new"

    def test_decorator_empty_path(self):
        router = BaseRouter()
        router.get()(Handlers.index)
        assert router.routes[0].path == "/"


class TestStatic:
    def test_static_route_added(self):
        router = BaseRouter()
        route = router.static("/assets", root="/tmp/assets")
        assert route in router.routes
        assert route.method == "GET"

    def test_static_route_with_name(self):
        router = BaseRouter()
        route = router.static("/assets", root="/tmp/assets", name="static")
        assert route.name == "static"

    def test_static_route_is_static_route_type(self):
        router = BaseRouter()
        route = router.static("/assets", root="/tmp/assets")
        from proper.router.route import StaticRoute
        assert isinstance(route, StaticRoute)


class TestResourceGroup:
    def test_resource_generates_all_crud_routes(self):
        router = BaseRouter()
        router.resource("photos")(PhotoController)
        # 8 routes: index, new, create, show, edit, update(PATCH), update(PUT), delete
        assert len(router.routes) == 8

    def test_resource_route_paths(self):
        router = BaseRouter()
        router.resource("photos")(PhotoController)
        paths = [(r.method, r.path) for r in router.routes]
        assert ("GET", "/photos") in paths
        assert ("GET", "/photos/new") in paths
        assert ("POST", "/photos") in paths
        assert ("GET", "/photos/:photo_id") in paths
        assert ("GET", "/photos/:photo_id/edit") in paths
        assert ("PATCH", "/photos/:photo_id") in paths
        assert ("PUT", "/photos/:photo_id") in paths
        assert ("DELETE", "/photos/:photo_id") in paths

    def test_resource_auto_pk_from_class_name(self):
        router = BaseRouter()
        router.resource("photos")(PhotoController)
        show_route = [r for r in router.routes if r.name == "Photo.show"][0]
        assert ":photo_id" in show_route.path

    def test_resource_custom_pk(self):
        router = BaseRouter()
        router.resource("photos", pk="uuid")(PhotoController)
        show_route = [r for r in router.routes if r.name == "Photo.show"][0]
        assert ":uuid" in show_route.path

    def test_resource_custom_pk_with_colon_prefix(self):
        """Regression: pk=':uuid' should not produce '::uuid' in the path."""
        router = BaseRouter()
        router.resource("photos", pk=":uuid")(PhotoController)
        show_route = [r for r in router.routes if r.name == "Photo.show"][0]
        assert ":uuid" in show_route.path
        assert "::uuid" not in show_route.path

    def test_resource_route_names(self):
        router = BaseRouter()
        router.resource("photos")(PhotoController)
        names = [r.name for r in router.routes]
        assert "Photo.index" in names
        assert "Photo.show" in names

    def test_resource_only_existing_actions(self):
        router = BaseRouter()
        router.resource("items")(PartialItemController)
        assert len(router.routes) == 2

    def test_resource_returns_class(self):
        router = BaseRouter()
        result = router.resource("photos")(PhotoController)
        assert result is PhotoController

    def test_resource_new_without_index_uses_root_path(self):
        router = BaseRouter()

        class NewOnlyController:
            def new(self): ...
            def create(self): ...

        router.resource("signup")(NewOnlyController)
        paths = [(r.method, r.path) for r in router.routes]
        assert ("GET", "/signup") in paths
        assert ("GET", "/signup/new") not in paths
        assert ("POST", "/signup") in paths


class TestResourceSingleton:
    def test_singleton_generates_routes(self):
        router = BaseRouter()
        router.resource("profile", pk=None)(ProfileController)
        # 7 routes: new, create, show, edit, update(PATCH), update(PUT), delete (no index)
        assert len(router.routes) == 7

    def test_singleton_no_pk_in_paths(self):
        router = BaseRouter()
        router.resource("profile", pk=None)(ProfileController)
        for r in router.routes:
            assert ":profile_id" not in r.path

    def test_singleton_paths(self):
        router = BaseRouter()
        router.resource("profile", pk=None)(ProfileController)
        paths = [(r.method, r.path) for r in router.routes]
        assert ("GET", "/profile/new") in paths
        assert ("POST", "/profile") in paths
        assert ("GET", "/profile") in paths
        assert ("GET", "/profile/edit") in paths
        assert ("PATCH", "/profile") in paths
        assert ("PUT", "/profile") in paths
        assert ("DELETE", "/profile") in paths

    def test_singleton_new_without_show_uses_root_path(self):
        router = BaseRouter()

        class NewOnlySingleton:
            def new(self): ...
            def create(self): ...

        router.resource("profile", pk=None)(NewOnlySingleton)
        paths = [(r.method, r.path) for r in router.routes]
        assert ("GET", "/profile") in paths
        assert ("GET", "/profile/new") not in paths
        assert ("POST", "/profile") in paths

    def test_singleton_no_index(self):
        router = BaseRouter()

        class ProfileWithIndex:
            def index(self): ...
            def show(self): ...

        router.resource("profile", pk=None)(ProfileWithIndex)
        names = [r.name for r in router.routes]
        assert "ProfileWithIndex.index" not in names


class TestScopedRouter:
    def test_scope_prefixes_routes(self):
        router = Router()
        api = router.scope("api")
        api.get("/photos")(Handlers.index)
        assert router.routes[0].path == "/api/photos"

    def test_scope_sets_host(self):
        router = Router()
        api = router.scope("api", host="api.example.com")
        api.get("/photos")(Handlers.index)
        assert router.routes[0].host == "api.example.com"

    def test_scope_routes_added_to_parent(self):
        router = Router()
        api = router.scope("api")
        api.get("/photos")(Handlers.index)
        assert len(router.routes) == 1
        assert len(api._routes) == 0

    def test_nested_scope(self):
        router = Router()
        api = router.scope("api")
        v1 = api.scope("v1")
        v1.get("/photos")(Handlers.index)
        assert router.routes[0].path == "/api/v1/photos"

    def test_nested_scope_host_inherited(self):
        router = Router()
        api = router.scope("api", host="api.example.com")
        v1 = api.scope("v1")
        v1.get("/photos")(Handlers.index)
        assert router.routes[0].host == "api.example.com"

    def test_nested_scope_host_overridden(self):
        router = Router()
        api = router.scope("api", host="api.example.com")
        v2 = api.scope("v2", host="v2.example.com")
        v2.get("/photos")(Handlers.index)
        assert router.routes[0].host == "v2.example.com"

    def test_scope_with_empty_prefix(self):
        router = Router()
        scoped = router.scope("", host="api.example.com")
        scoped.get("/photos")(Handlers.index)
        assert router.routes[0].path == "/photos"
        assert router.routes[0].host == "api.example.com"

    def test_scope_with_placeholder_prefix(self):
        router = Router()
        scoped = router.scope(":lang<en|es|pt>")
        scoped.get("/photos")(Handlers.index)
        route = router.routes[0]
        assert route.path == "/:lang<en|es|pt>/photos"
        matched, params = router.match("GET", "/en/photos")
        assert params["lang"] == "en"

    def test_scope_resource(self):
        router = Router()
        api = router.scope("api")
        api.resource("photos")(PhotoController)
        paths = [r.path for r in router.routes]
        assert "/api/photos" in paths
        assert any(":photo_id" in p for p in paths)

    def test_scope_post_decorator(self):
        router = Router()
        api = router.scope("api")
        api.post("/photos")(Handlers.create)
        assert router.routes[0].method == "POST"
        assert router.routes[0].path == "/api/photos"

    def test_scope_all_http_methods(self):
        router = Router()
        api = router.scope("api")
        api.put("/photos/:id")(Handlers.update)
        api.delete("/photos/:id")(Handlers.destroy)
        api.patch("/photos/:id")(Handlers.update)
        api.query("/search")(Handlers.search)
        api.options("/photos")(Handlers.opts)
        methods = [r.method for r in router.routes]
        assert "PUT" in methods
        assert "DELETE" in methods
        assert "PATCH" in methods
        assert "QUERY" in methods
        assert "OPTIONS" in methods


class TestRouter:
    def test_router_has_error_handlers(self):
        router = Router()
        assert router.error_handlers == {}

    def test_add_error_handler(self):
        router = Router()
        router.add_error_handler(ValueError, Handlers.action)
        assert router.error_handlers[ValueError] is Handlers.action

    def test_add_error_handler_rejects_non_exception(self):
        router = Router()
        with pytest.raises(AssertionError):
            router.add_error_handler("not_a_class", Handlers.action)

    def test_error_decorator(self):
        router = Router()
        result = router.error(ValueError)(Handlers.action)
        assert router.error_handlers[ValueError] is Handlers.action
        assert result is Handlers.action

    def test_router_debug_flag(self):
        router = Router(debug=True)
        assert router.debug is True

    def test_router_repr(self):
        router = Router()
        assert "<Router" in repr(router)


class TestConstants:
    def test_group_routes_count(self):
        assert len(GROUP_ROUTES) == 8

    def test_single_routes_count(self):
        assert len(SINGLE_ROUTES) == 7

    def test_group_routes_no_index_action_in_single(self):
        actions = [action for _, _, action in SINGLE_ROUTES]
        assert "index" not in actions

    def test_group_routes_has_pk(self):
        for _method, path, action in GROUP_ROUTES:
            if action in ("show", "edit", "update", "delete"):
                assert ":pk" in path

    def test_single_routes_no_pk(self):
        for _method, path, _action in SINGLE_ROUTES:
            assert ":pk" not in path


class TestEdgeCases:
    def test_match_empty_router(self):
        router = BaseRouter()
        with pytest.raises(MatchNotFound):
            router.match("GET", "/")

    def test_multiple_methods_same_path(self):
        router = BaseRouter()
        r_get = Route("GET", "/photos", name="list", to=Handlers.index)
        r_post = Route("POST", "/photos", name="create", to=Handlers.create)
        router.add_route(r_get)
        router.add_route(r_post)

        matched, _ = router.match("GET", "/photos")
        assert matched is r_get

        matched, _ = router.match("POST", "/photos")
        assert matched is r_post

    def test_url_for_and_match_roundtrip(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id<int>", name="photo", to=Handlers.action)
        router.add_route(r)

        url = router.url_for("photo", id=42)
        assert url == "/photos/42"

        matched, params = router.match("GET", url)
        assert matched is r
        assert params["id"] == 42

    def test_url_for_with_query_and_match(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)

        url = router.url_for("photos", page="2")
        path = url.split("?")[0]
        matched, _ = router.match("GET", path)
        assert matched is r

    def test_scope_url_for(self):
        router = Router()
        api = router.scope("api")
        api.get("/photos", name="api_photos")(Handlers.index)
        url = router.url_for("api_photos")
        assert url == "/api/photos"

    def test_match_method_not_allowed_vs_not_found(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)

        with pytest.raises(MethodNotAllowed):
            router.match("DELETE", "/photos")

        with pytest.raises(MatchNotFound):
            router.match("GET", "/videos")

    def test_match_with_special_chars_in_path(self):
        router = BaseRouter()
        r = Route("GET", "/api/v2.0/items", to=Handlers.action)
        router.add_route(r)
        matched, _ = router.match("GET", "/api/v2.0/items")
        assert matched is r

    def test_deeply_nested_scopes(self):
        router = Router()
        a = router.scope("a")
        b = a.scope("b")
        c = b.scope("c")
        c.get("/items")(Handlers.index)
        assert router.routes[0].path == "/a/b/c/items"

    def test_scope_with_resource_names_correct(self):
        router = Router()
        api = router.scope("api/v1")
        api.resource("photos")(PhotoController)
        assert router.routes[0].name == "Photo.index"
        assert router.routes[0].path == "/api/v1/photos"

    def test_redirect_route_in_match(self):
        router = BaseRouter()
        r = Route("GET", "/old-path", redirect="/new-path")
        router.add_route(r)
        matched, _ = router.match("GET", "/old-path")
        assert matched.redirect == "/new-path"
        assert matched.redirect_status == 307

    def test_custom_redirect_status(self):
        r = Route("GET", "/old", redirect="/new", redirect_status=301)
        assert r.redirect_status == 301

    def test_multiple_params_url_for_and_match(self):
        router = BaseRouter()
        r = Route("GET", "/:year<int>/:month<int>/:slug", name="article", to=Handlers.action)
        router.add_route(r)

        url = router.url_for("article", year=2024, month=1, slug="hello")
        assert url == "/2024/1/hello"

        matched, params = router.match("GET", "/2024/01/hello-world")
        assert params["year"] == 2024
        assert params["month"] == 1
        assert params["slug"] == "hello-world"

    def test_url_for_object_with_multiple_placeholders(self):
        router = BaseRouter()
        r = Route("GET", "/posts/:post_id/comments/:comment_id",
                   name="Comment.show", to=PostController.show)
        router.add_route(r)

        class Obj:
            post_id = 1
            comment_id = 2

        url = router.url_for("Comment.show", Obj())
        assert url == "/posts/1/comments/2"

    def test_route_with_regex_digit_format(self):
        router = BaseRouter()
        r = Route("GET", "/:year<\\d{4}>/:month<\\d{2}>/:day<\\d{2}>", to=Handlers.action)
        router.add_route(r)

        assert r.match("/2024/01/15") is not None
        assert r.match("/24/1/5") is None
        assert r.match("/abcd/ef/gh") is None

    def test_url_for_with_object_on_build_only_route(self):
        router = BaseRouter()
        r = Route("GET", "/things/:id", name="thing")
        router.add_route(r)

        class Thing:
            id = 7

        # Route has no .to, so cprefix falls back to ""
        url = router.url_for("thing", Thing())
        assert url == "/things/7"

    def test_url_is_uses_current_request_path(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)

        current.request = type("Request", (), {"path": "/photos"})()
        try:
            assert router.url_is("photos") is True
        finally:
            current.request = None

    def test_url_startswith_uses_current_request_path(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="photos", to=Handlers.action)
        router.add_route(r)

        current.request = type("Request", (), {"path": "/photos/42"})()
        try:
            assert router.url_startswith("photos") is True
        finally:
            current.request = None

    def test_scoped_router_without_parent(self):
        scoped = ScopedRouter("api")
        r = Route("GET", "/photos", to=Handlers.action)
        scoped.add_route(r)
        # Route path gets prefixed but is not delegated anywhere
        assert r.path == "/api/photos"
        # No parent means the route is not in any parent's list
        assert len(scoped._routes) == 0


class TestIndexedMatch:
    def test_static_route_indexed(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)
        assert ("GET", "/photos") in router._static_routes
        assert router._static_routes[("GET", "/photos")] is r

    def test_dynamic_route_indexed(self):
        router = BaseRouter()
        r = Route("GET", "/photos/:id", to=Handlers.action)
        router.add_route(r)
        assert ("GET", "/photos/:id") not in router._static_routes
        assert r in router._dynamic_routes["GET"]

    def test_build_only_excluded_from_indexes(self):
        router = BaseRouter()
        r = Route("GET", "/photos", name="build_only")
        router.add_route(r)
        assert ("GET", "/photos") not in router._static_routes
        assert "GET" not in router._dynamic_routes

    def test_host_route_goes_to_dynamic(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action, host="api.example.com")
        router.add_route(r)
        assert ("GET", "/photos") not in router._static_routes
        assert r in router._dynamic_routes["GET"]

    def test_allowed_by_path_populated(self):
        router = BaseRouter()
        router.add_route(Route("GET", "/photos", name="a", to=Handlers.action))
        router.add_route(Route("POST", "/photos", name="b", to=Handlers.create))
        assert router._allowed_by_path["/photos"] == {"GET", "POST"}

    def test_static_match_without_regex(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)
        matched, params = router.match("GET", "/photos")
        assert matched is r
        assert params == {}

    def test_static_match_with_trailing_slash(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action)
        router.add_route(r)
        matched, params = router.match("GET", "/photos/")
        assert matched is r

    def test_static_match_root(self):
        router = BaseRouter()
        r = Route("GET", "/", to=Handlers.action)
        router.add_route(r)
        matched, _ = router.match("GET", "/")
        assert matched is r

    def test_static_match_returns_defaults(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action, defaults={"format": "html"})
        router.add_route(r)
        _, params = router.match("GET", "/photos")
        assert params["format"] == "html"

    def test_mixed_static_and_dynamic(self):
        router = BaseRouter()
        r_static = Route("GET", "/photos", name="list", to=Handlers.index)
        r_dynamic = Route("GET", "/photos/:id", name="show", to=Handlers.show)
        router.add_route(r_static)
        router.add_route(r_dynamic)

        matched, _ = router.match("GET", "/photos")
        assert matched is r_static

        matched, params = router.match("GET", "/photos/42")
        assert matched is r_dynamic
        assert params["id"] == "42"

    def test_405_for_static_routes(self):
        router = BaseRouter()
        router.add_route(Route("GET", "/photos", name="a", to=Handlers.action))
        router.add_route(Route("POST", "/photos", name="b", to=Handlers.create))
        with pytest.raises(MethodNotAllowed) as exc_info:
            router.match("DELETE", "/photos")
        allow = exc_info.value.headers["Allow"]
        assert "GET" in allow
        assert "POST" in allow

    def test_405_combines_static_and_dynamic(self):
        router = BaseRouter()
        router.add_route(Route("GET", "/items", name="a", to=Handlers.index))
        router.add_route(Route("POST", "/items/:id", name="b", to=Handlers.create))
        # GET /items is static, POST /items/:id is dynamic
        # A DELETE to /items/42 should find POST via dynamic scan
        with pytest.raises(MethodNotAllowed) as exc_info:
            router.match("DELETE", "/items/42")
        allow = exc_info.value.headers["Allow"]
        assert "POST" in allow

    def test_dynamic_route_with_host_matches(self):
        router = BaseRouter()
        r = Route("GET", "/photos", to=Handlers.action, host="api.example.com")
        router.add_route(r)
        matched, _ = router.match("GET", "/photos", host="api.example.com")
        assert matched is r

    def test_resource_routes_indexed_correctly(self):
        router = BaseRouter()
        router.resource("photos")(PhotoController)
        # Static routes: GET /photos, GET /photos/new, POST /photos
        assert ("GET", "/photos") in router._static_routes
        assert ("GET", "/photos/new") in router._static_routes
        assert ("POST", "/photos") in router._static_routes
        # Dynamic routes: GET /photos/:photo_id, etc.
        assert any(
            r.path == "/photos/:photo_id"
            for r in router._dynamic_routes.get("GET", [])
        )


class TestChannelRegistration:
    def test_router_has_empty_channels(self):
        router = Router()
        assert router.channels == {}

    def test_channel_decorator_registers_class(self):
        router = Router()

        @router.channel("chat")
        class ChatChannel(Channel):
            pass

        assert "chat" in router.channels
        assert router.channels["chat"] is ChatChannel

    def test_channel_decorator_returns_class_unchanged(self):
        router = Router()

        @router.channel("chat")
        class ChatChannel(Channel):
            pass

        assert isinstance(ChatChannel, type)
        assert issubclass(ChatChannel, Channel)

    def test_multiple_channels(self):
        router = Router()

        @router.channel("chat")
        class ChatChannel(Channel):
            pass

        @router.channel()
        class NotificationChannel(Channel):
            pass

        assert len(router.channels) == 2
        assert "chat" in router.channels
        assert "NotificationChannel" in router.channels

    def test_channel_rejects_non_channel_subclass(self):
        router = Router()
        with pytest.raises(AssertionError, match="must be a subclass of Channel"):
            @router.channel("bad")
            class NotAChannel:
                pass

    def test_channel_name_not_required(self):
        router = Router()

        @router.channel()
        class ChatChannel(Channel):
            pass

        assert "ChatChannel" in router.channels


class TestNamespacePrefix:
    def test_no_controllers_segment(self):
        assert _namespace_prefix("myapp.views.post_controller") == ""

    def test_root_level_controller(self):
        assert _namespace_prefix("myapp.controllers.post_controller") == ""

    def test_single_subfolder(self):
        assert _namespace_prefix("myapp.controllers.admin.post_controller") == "Admin:"

    def test_nested_subfolders(self):
        assert _namespace_prefix("myapp.controllers.meh.foo_bar.post_controller") == "Meh:FooBar:"

    def test_snake_case_subfolder(self):
        assert _namespace_prefix("myapp.controllers.foo_bar.post_controller") == "FooBar:"

    def test_empty_module(self):
        assert _namespace_prefix("") == ""


class TestNamespacePrefixRouteNaming:
    def test_root_controller_route_name_unchanged(self):
        router = Router()
        router.resource("photos")(PhotoController)
        assert router.routes[0].name == "Photo.index"

    def test_subfolder_controller_resource_name(self):
        router = Router()

        class AdminPostController:
            __module__ = "myapp.controllers.admin.post_controller"
            def index(self): ...
            def show(self): ...

        router.resource("posts")(AdminPostController)
        assert router.routes[0].name == "Admin:AdminPost.index"

    def test_nested_subfolder_controller_resource_name(self):
        router = Router()

        class PostController:
            __module__ = "myapp.controllers.meh.foo_bar.post_controller"
            def index(self): ...

        router.resource("posts")(PostController)
        assert router.routes[0].name == "Meh:FooBar:Post.index"

    def test_subfolder_individual_route_name(self):
        router = BaseRouter()

        class PostController:
            __module__ = "myapp.controllers.admin.post_controller"
            def index(self): ...

        PostController.index.__module__ = PostController.__module__
        PostController.index.__qualname__ = "PostController.index"
        route = Route("GET", "/posts")
        route.to = PostController.index
        router.add_route(route)
        assert route.name == "Admin:Post.index"

    def test_url_for_with_namespace_prefix(self):
        router = BaseRouter()

        class PostController:
            __module__ = "myapp.controllers.admin.post_controller"
            def index(self): ...

        PostController.index.__module__ = PostController.__module__
        PostController.index.__qualname__ = "PostController.index"
        route = Route("GET", "/admin/posts")
        route.to = PostController.index
        router.add_route(route)
        assert router.url_for("Admin:Post.index") == "/admin/posts"

    def test_explicit_name_not_overridden(self):
        route = Route("GET", "/posts", name="custom_name")

        class PostController:
            __module__ = "myapp.controllers.admin.post_controller"
            def index(self): ...

        PostController.index.__module__ = PostController.__module__
        PostController.index.__qualname__ = "PostController.index"
        route.to = PostController.index
        assert route.name == "custom_name"
