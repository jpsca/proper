"""
Utilities to declare routes in your application.

"""

import re
import typing as t
from string import Template

from proper import status
from proper.errors import (
    BadRouteFormat,
    BadRoutePlaceholder,
    DuplicatedRoutePlaceholder,
    MissingRouteParameter,
)
from proper.types import THandler

from ..constants import DELETE, GET, OPTIONS, PATCH, POST, PUT, QUERY, RESTORE


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
    "restore",
    "query",
)

"""Formats to be replaced with regular expressions.
Note that these DOESN'T do any type conversion, just
validates the section of the route match the regular expression.
"""
FORMATS = {
    None: r"[^\/]+",
    "path": r".+",
    "int": r"[0-9]+",
    "float": r"[0-9]+\.[0-9]+",
}

RE_PLACEHOLDERS = re.compile(r":([_a-z][_a-z0-9]*)(?:<([^>]+)>)?")


class RouteTemplate(Template):
    delimiter = ":"


class Route:
    r"""
    Arguments:

    - method:
        Usualy, one of the HTTP methods: "get", "post", "put", "delete",
        "options", "patch", or "query"; but it could also be another
        application-specific value.

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    __slots__ = (
        "path",
        "path_re",
        "path_plain",
        "path_placeholders",
        "method",
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
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        self.method = method.upper()
        self.path = "/" + path.strip("/")
        self.path_re: re.Pattern | None = None
        self.path_plain: str | None = None
        self.path_placeholders: dict = {}
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

    def __eq__(self, other: t.Any) -> bool:
        if getattr(other, "__slots__", None) != self.__slots__:
            return NotImplemented
        return all(
            getattr(self, attr, None) == getattr(other, attr, None)
            for attr in self.__slots__
            if not attr.startswith("_") and not attr.startswith("path_")
        )

    @property
    def build_only(self) -> bool:
        """Is this a route only for `url_for()`
        and not for matching?"""
        return not (self.to or self.redirect)

    def compile_path(self) -> None:
        path = self.path
        parts = []
        parts_re = []
        placeholders = {}
        index = 0

        while True:
            match = RE_PLACEHOLDERS.search(path, pos=index)
            if not match:
                break
            start, end = match.span()
            part = path[index:start]
            parts.append(part)
            parts_re.append(re.escape(part))
            index = end

            name, rx = match.groups()
            if name in placeholders:
                raise DuplicatedRoutePlaceholder(name, path)

            rx = FORMATS.get(rx, rx)
            placeholders[name] = rx
            parts.append(f":{name}")
            parts_re.append(rf"(?P<{name}>{rx})")

        part = path[index:]
        if part:
            parts.append(part)
            parts_re.append(re.escape(part))

        str_re = r"".join(parts_re) + r"/?$"
        try:
            path_re = re.compile(str_re)
        except Exception as e:
            raise BadRouteFormat(e) from e

        self.path_re = path_re
        self.path_plain = "".join(parts)
        self.path_placeholders = placeholders

    def match(self, path: str) -> re.Match | None:
        if self.path_re is None:
            self.compile_path()

        assert self.path_re
        return self.path_re.match(path)

    def format(self, **kw) -> str:
        if self.path_plain is None:
            self.compile_path()

        tmpl = RouteTemplate(self.path_plain or "")
        path_params = self._get_path_params(kw)
        url = tmpl.substitute(dict(path_params)) or "/"

        query_params = self._get_query_params(path_params, kw)
        if query_params:
            params = "&".join([key + "=" + value for key, value in query_params.items()])
            url = url + "?" + params

        return url

    def _get_path_params(self, kwargs: dict) -> dict:
        path_params = {}

        for name, rx in self.path_placeholders.items():
            value = kwargs.get(name)
            if value is None:
                raise MissingRouteParameter(name, self.path)
            value = str(value)
            if not re.match(rx, value):
                raise BadRoutePlaceholder(name, self.path, rx)
            path_params[name] = value

        return path_params

    def _get_query_params(self, path_params: dict, kwargs: dict) -> dict:
        query_params = {}

        for name, value in kwargs.items():
            if name not in path_params:
                query_params[name] = value

        return query_params


class Get(Route):
    r"""GET route.

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            GET,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


class Post(Route):
    r"""POST route.

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            POST,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


class Put(Route):
    r"""PUT route.

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            PUT,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


class Delete(Route):
    r"""DELETE route.

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            DELETE,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


class Options(Route):
    r"""OPTIONS route.

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            OPTIONS,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


class Patch(Route):
    r"""PATCH route.

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            PATCH,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


class Query(Route):
    r"""A route for the new standard HTTP QUERY method.

    Like GET but with a body (yes, the standard doesn't forbid GET request
    to have a body, but that ship has sailed a long time ago).

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            QUERY,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


class Restore(Route):
    r"""A route for the non-standard HTTP RESTORE method.

    Yes, it's not standard, but so anything WebDAV or CalDAV, so sue me
    (no, better if you don't do it).

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

    - to:
        Optional. A reference to the view that this route is connected to.

    - name:
        Optional. Overwrites the default name of the route that is the qualified
        name of the `to` method. eg: `PagesView.show`.
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

    def __init__(
        self,
        path: str,
        *,
        to: THandler | None = None,
        name: str | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: str = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        super().__init__(
            RESTORE,
            path,
            to=to,
            name=name,
            host=host,
            redirect=redirect,
            redirect_status=redirect_status,
            defaults=defaults,
        )


route = Route
get = Get
post = Post
put = Put
delete = Delete
options = Options
patch = Patch
query = Query
restore = Restore
