"""
Utilities to declare routes in your application.

"""
from typing import Callable

from ..constants import GET, POST, PUT, DELETE, OPTIONS, PATCH, QUERY, RESTORE
from .base import BaseRoute


__all__ = (
    "Route",
    "Get",
    "Post",
    "Put",
    "Delete",
    "Options",
    "Patch",
    "Restore",
    "route",
    "get",
    "post",
    "put",
    "delete",
    "options",
    "patch",
    "static",
    "restore",
    "query",
)


class Route(BaseRoute):
    r"""
    Arguments are:

    method:
        Usualy, one of the HTTP methods: "get", "post", "put", "delete",
        "options", or "patch"; but it could also be another
        application-specific value.

    path:
        The path of this route. Can contain placeholders like `:name` or
        `:name<format>` where "format" can be:

        - nothing, for matching anything except slashes
        - `int` or `float`, for matching numbers
        - `path`, for matching anything *including* slashes
        - a regular expression

        Note that declaring a format doesn't make type conversions, **all values
        are passed to the view as strings**.

        Examples:

        - `docs/:lang<en|es|pt>`
        - `questions/:uuid`
        - `archive/:url<path>`
        - `:year<int>/:month<int>/:day<int>/:slug`
        - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

    to:
        Optional. A reference to the view that this route is connected to.

    name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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
    __slots__ = (
        "path_re",
        "path_plain",
        "path_placeholders",
        "method",
        "path",
        "to",
        "name",
        "host",
        "redirect",
        "redirect_status",
        "defaults",
    )

    def __init__(
        self,
        method: str,
        path: str,
        *,
        to: Callable | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = "307 Temporary Redirect",
        defaults: dict | None = None,
    ) -> None:
        super().__init__()
        self.method = method.upper()
        self.path = "/" + path.strip("/")
        self.to = to
        self.name = name or (to.__qualname__ if callable(to) else to)
        self.host = host
        self.redirect = redirect
        self.redirect_status = redirect_status
        self.defaults = defaults or {}

    def __repr__(self) -> str:
        return (
            f"<route {self.method} {self.path}"
            + (f" “{self.name}”" if self.name else "")
            + (f" host={ self.host}" if self.host else "")
            + (f" redirect={self.redirect} " if self.redirect else "")
            + ">"
        )

    @property
    def build_only(self) -> bool:
        """Is this a route only for `url_for()`
        and not for matching?"""
        return not (self.to or self.redirect)


class Get(Route):
    def __init__(self, path: str, **kw) -> None:
        super().__init__(GET, path, **kw)


class Post(Route):
    def __init__(self, path: str, **kw) -> None:
        super().__init__(POST, path, **kw)


class Put(Route):
    def __init__(self, path: str, **kw) -> None:
        super().__init__(PUT, path, **kw)


class Delete(Route):
    def __init__(self, path: str, **kw) -> None:
        super().__init__(DELETE, path, **kw)


class Options(Route):
    def __init__(self, path: str, **kw) -> None:
        super().__init__(OPTIONS, path, **kw)


class Patch(Route):
    def __init__(self, path: str, **kw) -> None:
        super().__init__(PATCH, path, **kw)


class Static(Route):
    """A route for static files."""

    def __init__(self, filepath: str) -> None:
        filepath = filepath.lstrip("/")
        redirect = f"/static/{filepath}"
        super().__init__("GET", filepath, redirect=redirect)


class Query(Route):
    """A route for the new standard HTTP QUERY method.

    Like GET but with a body (yes, the standard doesn't forbid GET request
    to have a body, but that ship has sailed a long time ago).

    Must be idempotent because the body WILL be cached. This also means
    that, like with a GET, the CSRF token will not be checked for QUERY requests.
    """
    def __init__(self, path: str, **kw) -> None:
        super().__init__(QUERY, path, **kw)


class Restore(Route):
    """A route for the non-standard HTTP RESTORE method.

    Yes, it's not standard, but so anything WebDAV or CalDAV, so sue me
    (no, better if you don't do it).

    Motivation: I feel that implementing a RESTful un-delete is ugly and hacky.
    A `/restore` is not restful and a PATCH is weird for undoing a DELETE
    So, form the ashes of uncertainty, rises... the HTTP RESTORE method.
    Someday it could be a RFC.
    """
    def __init__(self, path: str, **kw) -> None:
        super().__init__(RESTORE, path, **kw)


route = Route
get = Get
post = Post
put = Put
delete = Delete
options = Options
patch = Patch
static = Static
query = Query
restore = Restore
