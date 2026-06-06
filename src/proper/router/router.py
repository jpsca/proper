"""Router object that holds all routes and match them to urls.
"""
import inspect
import typing as t
from collections.abc import Callable
from pathlib import Path

import inflection

from .. import status
from ..channels import Channel
from ..constants import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_EDIT,
    ACTION_INDEX,
    ACTION_NEW,
    ACTION_SHOW,
    ACTION_UPDATE,
    DELETE,
    GET,
    OPTIONS,
    PATCH,
    POST,
    PUT,
    QUERY,
)
from ..errors import MatchNotFound, MethodNotAllowed, RouteNotFound
from ..global_context import current
from ..types import Iterable, TException, THandler
from .route import Route, StaticRoute, _namespace_prefix


if t.TYPE_CHECKING:
    from ..controller import Controller


__all__ = (
    "GROUP_ROUTES",
    "SINGLE_ROUTES",
    "TDecorator",
    "BaseRouter",
    "Router",
    "ScopedRouter",
)

GROUP_ROUTES = (
    (GET, "/", ACTION_INDEX),
    (GET, "/new", ACTION_NEW),
    (POST, "/", ACTION_CREATE),
    (GET, "/:pk", ACTION_SHOW),
    (GET, "/:pk/edit", ACTION_EDIT),
    (PATCH, "/:pk", ACTION_UPDATE),
    (PUT, "/:pk", ACTION_UPDATE),
    (DELETE, "/:pk", ACTION_DELETE),
)
SINGLE_ROUTES = (
    (GET, "/new", ACTION_NEW),
    (POST, "/", ACTION_CREATE),
    (GET, "/", ACTION_SHOW),
    (GET, "/edit", ACTION_EDIT),
    (PATCH, "/", ACTION_UPDATE),
    (PUT, "/", ACTION_UPDATE),
    (DELETE, "/", ACTION_DELETE),
)

TDecorator = Callable[[Callable], Callable]


class BaseRouter:
    """
    """
    debug: bool = False

    def __init__(self, *, debug: bool = False) -> None:
        self._routes: list[Route] = []
        self._routes_by_name: dict[str, Route] = {}
        self._static_routes: dict[tuple[str, str], Route] = {}
        self._dynamic_routes: dict[str, list[Route]] = {}
        self._allowed_by_path: dict[str, set[str]] = {}
        self.debug = debug

    def __repr__(self) -> str:
        return f"<Router #{id(self)}>"

    def add_route(self, route: Route) -> None:
        self._routes.append(route)
        if route.name and route.name not in self._routes_by_name:
            self._routes_by_name[route.name] = route

        if route.build_only:
            return

        if not route.path_placeholders and not route.host:
            # Static route - route.path is already normalized by the setter
            key = (route.method, route.path)
            if key not in self._static_routes:
                self._static_routes[key] = route
            if route.path not in self._allowed_by_path:
                self._allowed_by_path[route.path] = set()
            self._allowed_by_path[route.path].add(route.method)
        else:
            # Dynamic route (has placeholders or host constraint)
            if route.method not in self._dynamic_routes:
                self._dynamic_routes[route.method] = []
            self._dynamic_routes[route.method].append(route)

    def match(
        self,
        method: str,
        path: str,
        host: str | None = None,
    ) -> tuple[Route, dict]:
        """Takes a method and a path, that came from an URL,
        and tries to match them to a existing route

        Arguments:
            method:
                Usually, one of the HTTP methods: "get", "post", "put", "delete",
                "options", "patch", or "query"; but it could also be another
                application-specific value.
            path:
                The path of this route
            host:
                Optional. Host for this route, including any subdomain
                and an optional port. Examples: "www.example.com", "localhost:5000".

        Returns a matched `(route, params)`
        """
        normalized = path.rstrip("/") or "/"

        # Fast path: static routes (these never have a host constraint)
        route = self._static_routes.get((method, normalized))
        if route:
            params = route.defaults.copy() or {}
            return route, params

        # Dynamic routes: scan only those registered for this method
        dynamic = self._dynamic_routes.get(method, ())
        for route in dynamic:
            host_params = route.match_host(host)
            if host_params is None:
                continue
            m = route.match(path)
            if m is not None:
                params = route.defaults.copy() or {}
                params.update(host_params)
                params.update(m)
                return route, params

        # No match - collect allowed methods for 405 detection
        allowed = set()

        # Check static index (static routes never have host constraints)
        static_allowed = self._allowed_by_path.get(normalized)
        if static_allowed:
            allowed = static_allowed - {method}

        # Check dynamic routes for other methods
        for other_method, routes in self._dynamic_routes.items():
            if other_method == method:
                continue
            for route in routes:
                if route.match_host(host) is None:
                    continue
                if route.match(path) is not None:
                    allowed.add(other_method)
                    break

        if allowed:
            msg = f"`{path}` does not accept a `{method}`."
            raise MethodNotAllowed(msg, allowed=allowed)
        else:
            msg = f"{method} `{path}` does not match."
            raise MatchNotFound(msg)

    @property
    def routes(self) -> list[Route]:
        return self._routes

    def url_for(
        self,
        name: str,
        object: t.Any = None,
        *,
        _anchor: str = "",
        _full: bool = False,
        **kw,
    ) -> str:
        if name.startswith("/"):
            return name

        name = name.removesuffix("Controller")
        route = self._routes_by_name.get(name)
        if not route:
            raise RouteNotFound(name)

        if object is not None:
            if route.to:
                # Find the prefix for the placeholders of this route so if, for example, the route is
                # for `ItemController.action`, the placeholders `:item_id` and `:item_slug`,
                # are also searched as `id` and `slug` in the object attributes.
                cname = route.to.__qualname__.split(".")[0].removesuffix("Controller")
                cprefix = inflection.underscore(cname) + "_"
            else:
                cprefix = ""

            for key in route.path_placeholders:
                kw.setdefault(key, getattr(object, key, getattr(object, key.removeprefix(cprefix), None)))
            for key in route.host_placeholders:
                kw.setdefault(key, getattr(object, key, getattr(object, key.removeprefix(cprefix), None)))

        # Host placeholders are consumed by format_host(); strip them from path
        # kwargs so they don't leak into the query string.
        path_kw = {k: v for k, v in kw.items() if k not in route.host_placeholders}
        url = route.format(**path_kw)

        if _anchor:
            url += "#" + _anchor

        if _full and current.app:
            config = current.app.config
            host = route.format_host(**kw) if route.host_plain else config.HOST
            url = f"{config.PROTOCOL}://{host}{url}"

        return url

    def url_is(
        self,
        name: str,
        object: t.Any = None,
        *,
        curr_url: str = "",
        **kw,
    ) -> bool:
        control = self.url_for(name, object, **kw)
        if not curr_url and current.request:
            curr_url = current.request.path
        return curr_url.rstrip("/") == control.rstrip("/")

    def url_startswith(
        self,
        name: str,
        object: t.Any = None,
        *,
        curr_url: str = "",
        **kw,
    ) -> bool:
        control = self.url_for(name, object, **kw)
        if not curr_url and current.request:
            curr_url = current.request.path
        curr_url = curr_url.rstrip("/")

        if curr_url == control:
            return True
        if curr_url.startswith(f"{control}/"):
            return True
        return False

    def get(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: int = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> TDecorator:
        r"""Function or method decorator to register a GET route.

        Arguments:
            path:
                The path of this route. Can contain placeholders like `:name` or
                `:name<format>` where "format" can be:

                - nothing, for matching anything except slashes
                - `int` or `float`, for matching numbers
                - `path`, for matching anything *including* slashes
                - a regular expression

                The `int` and `float` formats also cast the matched value
                to the corresponding Python type.

                Examples:

                - `docs/:lang<en|es|pt>`
                - `questions/:uuid`
                - `archive/:url<path>`
                - `:year<int>/:month<int>/:day<int>/:slug`
                - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`
            name:
                Optional. Overwrites the default name of the route that is the qualified
                name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
                This name can be any unique string eg: "login", "index",
                "something.foobar", etc.
            host:
                Optional. Host for this route, including any subdomain
                and an optional port. Examples: "www.example.com", "localhost:5000".

                Like `path`, it can contain placeholders like `:name` or `:name<format>`
                with the same format rules.

                Examples:

                - :lang<en|es|pt>.example.com
                - :username.localhost:5000
            redirect:
                Optional. Instead of dispatching to a view, redirect to this
                other URL.
            redirect_status:
                Optional. Which status code to use for the redirect.
                The status "307 Temporary Redirect" is the default.
            defaults:
                Optional. A dict with extra values that will be sent to the view.

        """
        route = Route(
            method=GET,
            path=path,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )
        if redirect:
            self.add_route(route)
        return self._get_route_decorator(route)

    def options(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: int = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> TDecorator:
        """Decorator to register an OPTIONS route. See `get()` for argument details."""
        route = Route(
            method=OPTIONS,
            path=path,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )
        if redirect:
            self.add_route(route)
        return self._get_route_decorator(route)

    def post(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> TDecorator:
        """Decorator to register a POST route. See `get()` for argument details."""
        route = Route(
            method=POST,
            path=path,
            name=name,
            host=host,
            defaults=defaults,
        )
        return self._get_route_decorator(route)

    def put(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> TDecorator:
        """Decorator to register a PUT route. See `get()` for argument details."""
        route = Route(
            method=PUT,
            path=path,
            name=name,
            host=host,
            defaults=defaults,
        )
        return self._get_route_decorator(route)

    def delete(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> TDecorator:
        """Decorator to register a DELETE route. See `get()` for argument details."""
        route = Route(
            method=DELETE,
            path=path,
            name=name,
            host=host,
            defaults=defaults,
        )
        return self._get_route_decorator(route)

    def patch(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> TDecorator:
        """Decorator to register a PATCH route. See `get()` for argument details."""
        route = Route(
            method=PATCH,
            path=path,
            name=name,
            host=host,
            defaults=defaults,
        )
        return self._get_route_decorator(route)

    def query(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> TDecorator:
        """Decorator to register a QUERY route. See `get()` for argument details.

        A QUERY is like GET but with a body (although the HTTP standard doesn't
        forbid GET requests to have a body, that ship has sailed a long time ago).

        Must be idempotent because the body WILL be cached.
        """
        route = Route(
            method=QUERY,
            path=path,
            name=name,
            host=host,
            defaults=defaults,
        )
        return self._get_route_decorator(route)

    def static(
        self,
        url: str = "",
        *,
        root: str | Path,
        name: str | None = None,
        allowed_ext: Iterable[str] | None = (),
        public: bool = True,
        fingerprint: bool = True,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> Route:
        """A route for static files.

        Arguments:
            url:
                The base URL for these static files.
            root:
                The absolute path to the folder where the static files are.
            name:
                This name can be any unique string eg: "static", "files", "assets", etc.
            allowed_ext:
                Optional. If included, only the files with extensions on this list
                will be returned. Include `""` for files without any extension.
            public [True]:
                By default the Cache-Control header of static files is public, set this to
                `False` if you want the files to *not* be cacheable by other devices
                (like proxy caches).
            fingerprint:
                If True, inserts a hash of the updated time after the name of the file,
                but before the extension. This strategy encourages long-term caching while
                ensuring that new copies are only requested when the content changes, as
                any modification alters the fingerprint and thus the filename.
            host:
                Optional. Host for this route, including any subdomain
                and an optional port. Examples: "www.example.com", "localhost:5000".
            defaults:
                Optional. A dict with extra values that will be sent to the view.

        """
        route = StaticRoute(
            url,
            root=root,
            name=name,
            allowed_ext=allowed_ext,
            public=public,
            fingerprint=fingerprint,
            host=host,
            defaults=defaults,
        )
        self.add_route(route)
        return route

    def resource(
        self,
        path: str = "",
        *,
        pk: str | None = "",
    ) -> Callable:
        """Class decorator to add CRUD routes for a resource.

        Only the actions present in the class will be added.

        ## Group resource

        Example: `@router.resource("photos")`

        | HTTP     | PATH                  | ACTION   | USED FOR
        | -------- | -------------------   | -------- | -------------------------------
        | GET      | /photos                | index    | a list of all photos
        | GET      | /photos/new            | new      | form for creating a new photo
        | POST     | /photos                | create   | create a new photo
        | GET      | /photos/:photo_id      | show     | show a specific photo
        | GET      | /photos/:photo_id/edit | edit     | form for editing a specific photo
        | PATCH    | /photos/:photo_id      | update   | update a specific photo
        | PUT      | /photos/:photo_id      | update   | replace a specific photo
        | DELETE   | /photos/:photo_id      | delete   | delete a specific photo

        Note that both PATCH and PUT are routed to the `update` method.

        If a controller defines `new` but not `index` (or `show`, for singleton resources),
        the `new` action is mounted at `/resource-name` instead of `/resource-name/new`,
        since the root path is free.

        ## No ID

        Sometimes, you have a resource that clients always look up without referencing an ID.
        In this case, you can use `pk=None` to build a set of CRUD routes without `:obj_id`.

        Example: `@router.resource("profile", pk=None)`

        HTTP     PATH                ACTION   USED FOR
        -------- ------------------- -------- -------------------------------
        GET      /profile/new        new      form for creating the profile
        POST     /profile            create   create the profile
        GET      /profile            show     show the profile
        GET      /profile/edit       edit     form for editing the profile
        PATCH    /profile            update   update the profile
        PUT      /profile            update   replace the profile
        DELETE   /profile            delete   delete the profile

        In both scenarios, we validate the arguments first so we can show errors about what the user has
        typed instead of being about dynamically generated routes.

        """
        path = path.strip("/")

        def class_decorator(Controller: "type[Controller]") -> "type[Controller]":
            c_name = Controller.__name__.removesuffix("Controller")
            ns_prefix = _namespace_prefix(Controller.__module__)

            if pk is None:
                pk_ = ""
                valid_routes = SINGLE_ROUTES
            else:
                pk_ = pk.strip().strip(":")
                pk_ = f":{pk_}" if pk_ else f":{inflection.underscore(c_name)}_id"
                valid_routes = GROUP_ROUTES

            root_action = ACTION_SHOW if pk is None else ACTION_INDEX
            root_taken = getattr(Controller, root_action, None) is not None

            for http_method, action_path, action in valid_routes:
                method = getattr(Controller, action, None)
                if method is None:
                    continue

                if action == ACTION_NEW and not root_taken:
                    action_path = "/"

                if pk_:
                    action_path = action_path.replace(":pk", pk_)
                route = Route(
                    method=http_method,
                    path=f"{path}{action_path}",
                    name=f"{ns_prefix}{c_name}.{action}",
                    to=method,
                )
                self.add_route(route)

            return Controller

        return class_decorator

    def scope(self, prefix: str = "", *, host: str | None = None) -> "ScopedRouter":
        r"""
        Creates another router that set a prefix and a host to its routes.

        The returned scoped router can be also used to create *another* scoped router
        with a different host and/or with a prefix prepended to the original one.

        Arguments:
            prefix:
                Prefix for all routes under this scope. Can contain placeholders
                like `:name` or `:name<format>` where "format" can be:

                - nothing, for matching anything except slashes
                - `int` or `float`, for matching numbers
                - `path`, for matching anything *including* slashes
                - a regular expression

                Note that declaring a format doesn't make type conversions, **all values
                are passed to the view as strings**.

                Examples:

                - `docs/:lang<en|es|pt>`
                - `questions/:uuid`
                - `:year<int>/:month<int>`
                - `:year<\d{4}>/:month<\d{2}>`
            host:
                Optional. Host for all routes under this scope, including any subdomain
                and an optional port. Examples: "www.example.com", "localhost:5000".

                Like `mount`, it can contain placeholders like `:name` or `:name<format>`
                with the same format rules.

                Examples:

                - :lang<en|es|pt>.example.com
                - :username.localhost:5000

        """
        return ScopedRouter(prefix, host=host, parent=self, debug=self.debug)

    # Private

    def _get_route_decorator(self, route: Route) -> TDecorator:
        def _decorator(to) -> Callable:
            route.to = to
            self.add_route(route)
            return to

        return _decorator


class Router(BaseRouter):
    # A dict of functions to call when an HTTPError is raised.
    # The keys are any subclasses of Exception
    error_handlers: dict[TException, THandler]

    # Registered channel classes, keyed by name (e.g. "ChatChannel")
    channels: "dict[str, type[Channel]]"

    def __init__(self, *, debug: bool = False) -> None:
        self.error_handlers = {}
        self.channels = {}
        super().__init__(debug=debug)

    def add_error_handler(self, error_cls: TException, to: THandler) -> None:
        is_exception = inspect.isclass(error_cls) and issubclass(error_cls, BaseException)
        assert is_exception, "`error_cls` must be a subclass of `Exception`"
        self.error_handlers[error_cls] = to

    def channel(self, name: str = "") -> "Callable[[type[Channel]], type[Channel]]":
        """Class decorator to register a WebSocket channel.

        Example:

        ```python
        @router.channel("chat")
        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from(f"chat_{self.params['room']}")
        ```

        The `name` argument is used as a URL-friendly identifier for routing.
        If omitted, it is derived from the class name (e.g. "ChatChannel" -> "chat").

        The channel class is registered under its full class name (e.g. "ChatChannel")
        which is what clients use to subscribe.
        """
        def class_decorator(cls: type[Channel]) -> type[Channel]:
            assert issubclass(cls, Channel), (
                f"{cls.__name__} must be a subclass of Channel"
            )
            self.channels[name or cls.__name__] = cls
            return cls

        return class_decorator

    def error(self, error_cls: TException) -> Callable[[Callable], Callable]:
        """Decorator to register a controller method to handle errors by exception class.
        Example:

        ```python
        class Pages(Controller):
            @app.router.error(errors.NotFound)
            def not_found(self):
                ...
        ```
        """
        def _decorator(to) -> Callable:
            self.add_error_handler(error_cls, to)
            return to

        return _decorator


class ScopedRouter(BaseRouter):
    r"""
    A ScopedRouter is a convenient shortcut to set a prefix and a host to a group
    of routes.

    Arguments:
        prefix:
            Prefix for all routes under this scope. Can contain placeholders
            like `:name` or `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions, **all values
            are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `:year<int>/:month<int>`
            - `:year<\d{4}>/:month<\d{2}>`
        host:
            Optional. Host for all routes under this scope, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `mount`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

    """

    prefix: str
    host: str | None

    def __init__(
        self,
        prefix: str = "",
        *,
        host: str | None = None,
        parent: BaseRouter | None = None,
        debug: bool = False,
    ) -> None:
        self.prefix = prefix.strip("/")
        self.host = host
        self._parent = parent
        super().__init__(debug=debug)

    def __repr__(self) -> str:
        return (
            f"<ScopedRouter '{self.prefix}'"
            + (f" host={self.host}" if self.host else "")
            + f" #{id(self)}>"
        )

    def add_route(self, route: Route) -> None:
        if self.prefix:
            route.path = f"{self.prefix}{route.path}"
        if self.host:
            route.host = self.host
        if self._parent:
            self._parent.add_route(route)

    def scope(self, prefix: str = "", *, host: str | None = None) -> "ScopedRouter":
        """Like `BaseRouter.scope()`, but appends to the current prefix
        and inherits the parent host if not overridden."""
        prefix = f"{self.prefix}/{prefix.strip('/')}"
        host = host or self.host
        return ScopedRouter(prefix, host=host, parent=self._parent, debug=self.debug)
