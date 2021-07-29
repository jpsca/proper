"""
Utilities to declare routes in your application.

"""
from typing import Callable, Dict, Optional

from .base import BaseRoute


__all__ = (
    "Route",
    "Get",
    "Post",
    "Put",
    "Delete",
    "Options",
    "Patch",
    "route",
    "get",
    "post",
    "put",
    "delete",
    "options",
    "patch",
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
        are passed to the controller as strings**.

        Examples:

        - `docs/:lang<en|es|pt>`
        - `questions/:uuid`
        - `archive/:url<path>`
        - `:year<int>/:month<int>/:day<int>/:slug`
        - `:year<\d{4}>/:month<\d{2}>/:day<\d{2}>/:slug`

    to:
        Optional. A reference to the controller that this route is connected to.

    name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesController.show`.
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
        Optional. Instead of dispatching to a controller, redirect to this
        other URL.

    redirect_status_code:
        Optional. Which status code to use for the redirect.
        The status "307 Temporary Redirect" is the default.

    defaults:
        Optional. A dict with extra values that will be sent to the controller.

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
        "redirect_status_code",
        "defaults",
    )

    def __init__(
        self,
        method: str,
        path: str,
        *,
        to: Optional[Callable] = None,
        name: Optional[str] = None,
        host: Optional[str] = None,
        redirect: Optional[str] = None,
        redirect_status_code: str = "307 Temporary Redirect",
        defaults: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__()
        self.method = method.upper()
        self.path = "/" + path.strip("/")
        self.to = to
        self.name = name or (to.__qualname__ if callable(to) else to)
        self.host = host
        self.redirect = redirect
        self.redirect_status_code = redirect_status_code
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
    def __init__(self, path: str, **kwargs) -> None:
        super().__init__("GET", path, **kwargs)


class Post(Route):
    def __init__(self, path: str, **kwargs) -> None:
        super().__init__("POST", path, **kwargs)


class Put(Route):
    def __init__(self, path: str, **kwargs) -> None:
        super().__init__("PUT", path, **kwargs)


class Delete(Route):
    def __init__(self, path: str, **kwargs) -> None:
        super().__init__("DELETE", path, **kwargs)


class Options(Route):
    def __init__(self, path: str, **kwargs) -> None:
        super().__init__("OPTIONS", path, **kwargs)


class Patch(Route):
    def __init__(self, path: str, **kwargs) -> None:
        super().__init__("PATCH", path, **kwargs)


route = Route
get = Get
post = Post
put = Put
delete = Delete
options = Options
patch = Patch
