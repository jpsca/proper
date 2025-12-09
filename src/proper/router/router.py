"""Router object that holds all routes and match them to urls.
"""
import inspect
import typing as t
from pathlib import Path

from proper import status
from proper.controller import Controller
from proper.core.global_context import current
from proper.errors import MatchNotFound, MethodNotAllowed, RouteNotFound
from proper.types import TException, THandler, TIterable
from ..constants import DELETE, GET, OPTIONS, PATCH, POST, PUT, QUERY, RESTORE
from .route import Route, StaticRoute


__all__ = (
    "ACTION_INDEX",
    "ACTION_NEW",
    "ACTION_CREATE",
    "ACTION_SHOW",
    "ACTION_EDIT",
    "ACTION_UPDATE",
    "ACTION_DELETE",
    "ACTION_RESTORE",
    "GROUP_ROUTES",
    "SINGLE_ROUTES",
    "TDecorator",
    "BaseRouter",
    "Router",
    "ScopedRouter",
)

ACTION_INDEX = "index"
ACTION_NEW = "new"
ACTION_CREATE = "create"
ACTION_SHOW = "show"
ACTION_EDIT = "edit"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_RESTORE = "restore"

GROUP_ROUTES = (
    (GET, "/", ACTION_INDEX),
    (GET, "/new", ACTION_NEW),
    (POST, "/", ACTION_CREATE),
    (GET, "/:pk", ACTION_SHOW),
    (GET, "/:pk/edit", ACTION_EDIT),
    (PATCH, "/:pk", ACTION_UPDATE),
    (PUT, "/:pk", ACTION_UPDATE),
    (DELETE, "/:pk", ACTION_DELETE),
    (RESTORE, "/:pk", ACTION_RESTORE),
)
SINGLE_ROUTES = (
    (GET, "/new", ACTION_NEW),
    (POST, "/", ACTION_CREATE),
    (GET, "/", ACTION_SHOW),
    (GET, "/edit", ACTION_EDIT),
    (PATCH, "/", ACTION_UPDATE),
    (PUT, "/", ACTION_UPDATE),
    (DELETE, "/", ACTION_DELETE),
    (RESTORE, "/", ACTION_RESTORE),
)

TDecorator = t.Callable[[t.Callable], t.Callable]


class BaseRouter:
    """
    """
    debug: bool = False

    def __init__(self, *, debug: bool = False) -> None:
        self._routes: list[Route] = []
        self._routes_by_name: dict[str, Route] = {}
        self.debug = debug

    def __repr__(self) -> str:
        return f"<Router #{id(self)}>"

    def add_route(self, route: Route) -> None:
        self._routes.append(route)
        if route.name:
            self._routes_by_name[route.name] = route

    def match(
        self,
        method: str,
        path: str,
        host: str | None = None,
    ) -> tuple[Route, dict]:
        """Takes a method and a path, that came from an URL,
        and tries to match them to a existing route

        Arguments are:

        method:
            Usualy, one of the HTTP methods: "get", "post", "put", "delete",
            "options", "patch", or "query"; but it could also be another
            application-specific value.

        path:
            The path of this route

        host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

        Returns a matched `(route, params)`
        """
        # If the path match but the method do not, we need to return
        # a list of the allowed methods with the 405 response.
        allowed = set()
        for route in self.routes:
            if route.host is not None and route.host != host:
                continue
            match = route.match(path)
            if not match:
                continue
            if route.method != method:
                allowed.add(route.method)
                continue

            if not (route.to or route.redirect):
                # build-only route
                continue

            params = route.defaults.copy() or {}
            params.update(match.groupdict())

            return route, params

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
        **kw,
    ) -> str:
        if name.startswith("/"):
            return name

        name = name.removesuffix("Controller")
        route = self._routes_by_name.get(name)
        if not route:
            raise RouteNotFound(name)

        if object is not None:
            for key in route.path_placeholders:
                kw.setdefault(key, getattr(object, key))

        url = route.format(**kw)

        if _anchor:
            url += "#" + _anchor

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
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> TDecorator:
        r"""Function or method decorator to register a GET route.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        - redirect:
            Optional. Instead of dispatching to a view, redirect to this
            other URL.

        - redirect_status:
            Optional. Which status code to use for the redirect.
            The status "307 Temporary Redirect" is the default.

        - defaults:
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
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> TDecorator:
        r"""Function or method decorator to register a OPTIONS route.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

                    - redirect:
            Optional. Instead of dispatching to a view, redirect to this
            other URL.

        - redirect_status:
            Optional. Which status code to use for the redirect.
            The status "307 Temporary Redirect" is the default.

        - defaults:
            Optional. A dict with extra values that will be sent to the view.

        """
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
        r"""Method decorator to register a POST route.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        - defaults:
            Optional. A dict with extra values that will be sent to the view.

        """
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
        r"""Method decorator to register a PUT route.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        - defaults:
            Optional. A dict with extra values that will be sent to the view.

        """
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
        r"""Method decorator to register a DELETE route.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        - defaults:
            Optional. A dict with extra values that will be sent to the view.

        """
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
        r"""Method decorator to register a PATCH route.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        - defaults:
            Optional. A dict with extra values that will be sent to the view.

        """
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
        r"""Method decorator to register a QUERY route.

        A QUERY is like GET but with a body (although the HTTP standard doesn't
        forbid GET requests to have a body, that ship has sailed a long time ago).

        Must be idempotent because the body WILL be cached. This also means
        that, like with a GET, the CSRF token will not be checked for QUERY requests.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        - defaults:
            Optional. A dict with extra values that will be sent to the view.

        """
        route = Route(
            method=QUERY,
            path=path,
            name=name,
            host=host,
            defaults=defaults,
        )
        return self._get_route_decorator(route)

    def restore(
        self,
        path: str = "",
        *,
        name: str | None = None,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> TDecorator:
        r"""Method decorator to register a non-standard HTTP RESTORE route.

        Yes, it's not standard, but so anything WebDAV or CalDAV, so sue me
        (it's a figure of speech, best if you don't do it).

        Motivation: I feel that implementing a RESTful un-delete is ugly and hacky.
        A `/restore` is not restful and a PATCH is weird for undoing a DELETE
        So, form the ashes of uncertainty, rises... the HTTP RESTORE method.
        Someday it could be a RFC.

        Arguments:

        - path:
            The path of this route. Can contain placeholders like `:name` or
            `:name<format>` where "format" can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

            Note that declaring a format doesn't make type conversions,
            **all values are passed to the view as strings**.

            Examples:

            - `docs/:lang<en|es|pt>`
            - `questions/:uuid`
            - `archive/:url<path>`
            - `:year<int>/:month<int>/:day<int>/:slug`
            - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

        - name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method minus the "Controller" suffix, eg: `Page.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `path`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        - defaults:
            Optional. A dict with extra values that will be sent to the view.

        """
        route = Route(
            method=RESTORE,
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
        allowed_ext: TIterable[str] | None = (),
        public: bool = True,
        fingerprint: bool = True,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> Route:
        """A route for static files.

        Arguments:

        - url:
            The base URL for these static files.

        - root:
            The absolute path to the folder where the static files are.

        - name:
            This name can be any unique string eg: "static", "files", "assets", etc.

        - allowed_ext:
            Optional. If included, only the files with extensions on this list
            wil be returned. Include `""` for files without any extension.

        - public [True]:
            By default the Cache-Control header of static files is public, set this to
            `False` if you want the files to *not* be cacheable by other devices
            (like proxy caches).

        - fingerprint [True]:
            If True, adds, insert a hash of the updated time after the name of the file,
            but before the extension. This strategy encourages long-term caching while
            ensuring that new copies are only requested when the content changes, as
            any modification alters the fingerprint and thus the filename.

        - host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

        - defaults:
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
        singular: bool = False,
    ) -> t.Callable:
        """Class decorator to add REST routes for a resource.

        Only the actions present in the class will be added.

        ## Group resource

        Example: `@router.resource("photos")`

        HTTP     PATH                ACTION   USED FOR
        -------- ------------------- -------- -------------------------------
        GET      /photos             index    a list of all photos
        GET      /photos/new         new      form for creating a new photo
        POST     /photos             create   create a new photo
        GET      /photos/:pk         show     show a specific photo
        GET      /photos/:pk/edit    edit     form for editing a specific photo
        PATCH    /photos/:pk         update   update a specific photo
        PUT      /photos/:pk         update   replace a specific photo
        DELETE   /photos/:pk         delete   delete a specific photo
        RESTORE  /photos/:pk         restore  restore a specific photo

        Note that both PATCH and PUT are routed to the `update` method.

        ## Singular resource

        Sometimes, you have a resource that clients always look up without referencing an ID.
        In this case, you can use `singular=True` to build a set of REST routes without `:pk`.

        Example: `@router.resource("profile", singular=True)`

        HTTP     PATH                ACTION   USED FOR
        -------- ------------------- -------- -------------------------------
        GET      /profile/new        new      form for creating the profile
        POST     /profile            create   create the profile
        GET      /profile            show     show the profile
        GET      /profile/edit       edit     form for editing the profile
        PATCH    /profile            update   update the profile
        PUT      /profile            update   replace the profile
        DELETE   /profile            delete   delete the profile
        RESTORE  /profile            restore  restore the profile

        In both scenarios, we validate the arguments first so we can show errors about what the user has
        typed instead of being about dynamically generated routes.

        """
        path = path.strip("/")
        valid_routes = SINGLE_ROUTES if singular else GROUP_ROUTES

        def class_decorator(Controller: type[Controller]) -> type[Controller]:
            c_name = Controller.__name__.removesuffix("Controller")

            for http_method, action_path, action in valid_routes:
                method = getattr(Controller, action, None)
                if method is None:
                    continue

                route = Route(
                    method=http_method,
                    path=f"{path}{action_path}",
                    name=f"{c_name}.{action}",
                    to=method,
                    defaults={"controller": c_name},
                )
                self.add_route(route)

            return Controller

        return class_decorator

    def scope(self, prefix: str = "", *, host: str | None = None) -> "ScopedRouter":
        r"""
        Creates another router that set a prefix and a host to its routes.

        The returned scoped router can be also used to create *another* scoped router
        with a different host and/or with a prefix prepended to the original one.

        Arguments are:

        prefix (str):
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

        host (str):
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
        def _decorator(to) -> t.Callable:
            route.to = to
            self.add_route(route)
            return to

        return _decorator


class Router(BaseRouter):
    # A dict of functions to call when an HTTPError is raised.
    # The keys are any subclasses of Exception
    error_handlers: dict[TException, THandler]

    def __init__(self, *, debug: bool = False) -> None:
        self.error_handlers = {}
        super().__init__(debug=debug)

    def add_error_handler(self, error_cls: TException, to: THandler) -> None:
        is_exception = inspect.isclass(error_cls) and issubclass(error_cls, BaseException)
        assert is_exception, "`error_cls` must a subclass of `Exception`"
        self.error_handlers[error_cls] = to

    def error(self, error_cls: TException) -> t.Callable[[t.Callable], t.Callable]:
        """Decorator to register a controller method to handle errors by exception class.
        If debug=True, it also adds a route to preview that page.

        Example:

        ```python
        class Pages(Controller):
            @app.router.error(errors.NotFound)
            def not_found(self):
                ...
        , Page.not_found)
        app.error_handler(Exception, Page.error)
        ```
        """
        def _decorator(to) -> t.Callable:
            self.add_error_handler(error_cls, to)
            return to

        return _decorator


class ScopedRouter(BaseRouter):
    r"""
    A ScopedRouter is a convenient shortcut to set a prefix and a host to a group
    of routes.

    Arguments are:

    prefix (str):
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

    host (str):
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
            + f" host={self.host}" if self.host else ""
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
        r"""
        Creates another router that set a prefix and a host to its routes.
        The prefix is appended to the current prefix.
        The host is replaced if defined, otherwise the parent host is used.

        Arguments are:

        prefix (str):
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

        host (str):
            Optional. Host for all routes under this scope, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

            Like `mount`, it can contain placeholders like `:name` or `:name<format>`
            with the same format rules.

            Examples:

            - :lang<en|es|pt>.example.com
            - :username.localhost:5000

        """
        prefix = f"{self.prefix}/{prefix.strip('/')}"
        host = host or self.host
        return ScopedRouter(prefix, host=host, parent=self._parent, debug=self.debug)
