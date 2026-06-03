"""
Utilities to declare routes in your application.

"""

import os
import re
import typing as t
from hashlib import sha256
from pathlib import Path
from string import Template

import inflection

from .. import status
from ..constants import GET
from ..controller import StaticFilesController
from ..errors import (
    BadRouteFormat,
    BadRoutePlaceholder,
    DuplicatedRoutePlaceholder,
    MissingRouteParameter,
)
from ..types import Iterable, THandler


__all__ = (
    "FORMATS",
    "RouteTemplate",
    "Route",
    "StaticRoute",
)

"""Formats to be replaced with regular expressions.
Note that these DON'T do any type conversion, just
validates the section of the route match the regular expression.
"""
FORMATS = {
    None: r"[^\/]+",
    "path": r".+",
    "int": r"[0-9]+",
    "float": r"[0-9]+\.[0-9]+",
}

RE_PLACEHOLDERS = re.compile(r":([_a-z][_a-z0-9]*)(?:<([^>]+)>)?")


def _compile_pattern(
    pattern: str, *, anchor_suffix: str = ""
) -> tuple[re.Pattern, str, dict, dict]:
    """Compile a placeholder-aware pattern (path or host).

    Returns a 4-tuple of:

    - the compiled regex (with named groups for each placeholder),
    - a "plain" template string with `:name` markers preserved (for `RouteTemplate`),
    - a dict of placeholder name → regex source,
    - a dict of placeholder name → type caster (only for `int`/`float`).
    """
    parts: list[str] = []
    parts_re: list[str] = []
    placeholders: dict = {}
    casters: dict = {}
    index = 0

    while True:
        match = RE_PLACEHOLDERS.search(pattern, pos=index)
        if not match:
            break
        start, end = match.span()
        part = pattern[index:start]
        parts.append(part)
        parts_re.append(re.escape(part))
        index = end

        name, fmt = match.groups()
        if name in placeholders:
            raise DuplicatedRoutePlaceholder(name, pattern)

        if fmt == "int":
            casters[name] = int
        elif fmt == "float":
            casters[name] = float

        rx = FORMATS.get(fmt, fmt)
        placeholders[name] = rx
        parts.append(f":{name}")
        parts_re.append(rf"(?P<{name}>{rx})")

    tail = pattern[index:]
    if tail:
        parts.append(tail)
        parts_re.append(re.escape(tail))

    str_re = r"".join(parts_re) + anchor_suffix
    try:
        compiled = re.compile(str_re)
    except Exception as e:
        raise BadRouteFormat(e) from e

    return compiled, "".join(parts), placeholders, casters


class RouteTemplate(Template):
    delimiter = ":"


def _namespace_prefix(module: str) -> str:
    parts = module.split(".")
    try:
        idx = parts.index("controllers")
    except ValueError:
        return ""
    middle = parts[idx + 1 : -1]
    if not middle:
        return ""
    return ":".join(inflection.camelize(seg) for seg in middle) + ":"


class Route:
    r"""
    Arguments:
        method:
            Usually, one of the HTTP methods: "get", "post", "put", "delete",
            "options", "patch", or "query"; but it could also be another
            application-specific value.
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
        to:
            Optional. A reference to the view that this route is connected to.
        name:
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method. eg: `Pages.show`.
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

    def __init__(
        self,
        method: str,
        path: str,
        *,
        name: str | None = None,
        to: THandler | None = None,
        host: str | None = None,
        redirect: str | None = None,
        redirect_status: int = status.temporary_redirect,
        defaults: dict | None = None,
    ) -> None:
        self.name = name
        self.host = host
        self.redirect = redirect
        self.redirect_status = redirect_status
        self.defaults = defaults or {}

        self.method = method
        self.path = path
        self.to = to

    @property
    def method(self) -> str:
        return self._method

    @method.setter
    def method(self, value: str):
        self._method = value.upper()

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, value: str):
        self._path = "/" + value.strip("/")
        self._compile_path()

    @property
    def host(self) -> str | None:
        return self._host

    @host.setter
    def host(self, value: str | None):
        self._host = value
        self._compile_host()

    @property
    def to(self) -> THandler | None:
        return self._to

    @to.setter
    def to(self, value: THandler | None):
        self._to = value
        if not self.name and value:
            cls, method = value.__qualname__.rsplit(".", 1)
            prefix = _namespace_prefix(getattr(value, "__module__", "") or "")
            self.name = f"{prefix}{cls.removesuffix('Controller')}.{method}"

    def __repr__(self) -> str:
        return (
            f"<route {self.method} {self.path}"
            + (f" '{self.name}'" if self.name else "")
            + (f" host={self.host}" if self.host else "")
            + (f" redirect={self.redirect} " if self.redirect else "")
            + ">"
        )

    def __eq__(self, other: t.Any) -> bool:
        for attr in (
            "method",
            "path",
            "to",
            "name",
            "host",
            "redirect",
            "redirect_status",
            "defaults",
        ):
            if not hasattr(other, attr) or getattr(self, attr) != getattr(other, attr):
                return False
        return True

    @property
    def build_only(self) -> bool:
        """Is this a route only for `url_for()`
        and not for matching?"""
        return not (self.to or self.redirect)

    def match(self, path: str) -> dict | None:
        assert self.path_re
        m = self.path_re.match(path)
        if m is None:
            return None
        params = m.groupdict()
        for name, caster in self.path_casters.items():
            if name in params:
                params[name] = caster(params[name])
        return params

    def match_host(self, host: str | None) -> dict | None:
        """Match a request host against this route's host pattern.

        Returns:

        - `None` if the route has a host constraint that doesn't apply.
        - An empty dict `{}` if the route has no host constraint
          (always matches, no extra params).
        - A dict of captured placeholder values if the host pattern matches.
        """
        if self.host_re is None:
            return {}
        if host is None:
            return None
        m = self.host_re.match(host)
        if m is None:
            return None
        params = m.groupdict()
        for name, caster in self.host_casters.items():
            if name in params:
                params[name] = caster(params[name])
        return params

    def format(self, **kw) -> str:
        tmpl = RouteTemplate(self.path_plain or "")
        path_params = self._get_path_params(kw)
        url = tmpl.substitute(dict(path_params)) or "/"

        query_params = self._get_query_params(path_params, kw)
        if query_params:
            params = "&".join([f"{key}={value}" for key, value in query_params.items()])
            url = url + "?" + params

        return url

    def format_host(self, **kw) -> str | None:
        """Build the host string for this route, substituting placeholders.

        Returns `None` if the route has no host constraint.
        """
        if self.host_plain is None:
            return None
        tmpl = RouteTemplate(self.host_plain)
        host_params = self._get_host_params(kw)
        return tmpl.substitute(dict(host_params))

    # Private

    def _compile_path(self) -> None:
        path_re, path_plain, placeholders, casters = _compile_pattern(
            self.path, anchor_suffix=r"/?$"
        )
        self.path_re = path_re
        self.path_plain = path_plain
        self.path_placeholders = placeholders
        self.path_casters = casters

    def _compile_host(self) -> None:
        if self._host is None:
            self.host_re = None
            self.host_plain = None
            self.host_placeholders = {}
            self.host_casters = {}
            return
        host_re, host_plain, placeholders, casters = _compile_pattern(
            self._host, anchor_suffix=r"$"
        )
        self.host_re = host_re
        self.host_plain = host_plain
        self.host_placeholders = placeholders
        self.host_casters = casters

    def _get_path_params(self, kwargs: dict) -> dict:
        return self._get_pattern_params(
            self.path_placeholders, kwargs, source=self.path
        )

    def _get_host_params(self, kwargs: dict) -> dict:
        return self._get_pattern_params(
            self.host_placeholders, kwargs, source=self.host or ""
        )

    @staticmethod
    def _get_pattern_params(placeholders: dict, kwargs: dict, *, source: str) -> dict:
        params = {}
        for name, rx in placeholders.items():
            value = kwargs.get(name)
            if value is None:
                raise MissingRouteParameter(name, source)
            value = str(value)
            if not re.match(rx, value):
                raise BadRoutePlaceholder(name, source, rx)
            params[name] = value
        return params

    def _get_query_params(self, path_params: dict, kwargs: dict) -> dict:
        query_params = {}

        for name, value in kwargs.items():
            if name not in path_params:
                query_params[name] = value

        return query_params


class StaticRoute(Route):
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
        fingerprint [True]:
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

    def __init__(
        self,
        url: str,
        *,
        root: str | Path,
        name: str | None = None,
        allowed_ext: Iterable[str] | None = (),
        public: bool = True,
        fingerprint: bool = True,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> None:
        defaults = defaults or {}
        defaults["url"] = url
        defaults["root"] = root
        defaults["public"] = bool(public)
        defaults["fp"] = bool(fingerprint)
        if allowed_ext:
            defaults["allowed_ext"] = allowed_ext
        path = f"{url.strip('/')}/:file<path>"

        super().__init__(
            GET,
            path,
            to=StaticFilesController.show,
            name=name,
            host=host,
            defaults=defaults,
        )

    def format(self, **kw) -> str:
        if not self.defaults["fp"]:
            return super().format(**kw)

        if "file" not in kw:
            raise MissingRouteParameter("file", self.path)

        root = Path(self.defaults["root"])
        filename: str = kw["file"]
        relpath = Path(filename.lstrip(os.path.sep))
        filepath = root / relpath
        if not filepath.is_file():
            return super().format(**kw)

        stat = filepath.stat()
        fingerprint = sha256(str(stat.st_mtime).encode()).hexdigest()

        ext = "".join(relpath.suffixes)
        stem = relpath.name.removesuffix(ext)
        parent = str(relpath.parent)
        parent = "" if parent == "." else f"{parent}/"

        kw["file"] = f"{parent}{stem}-{fingerprint}{ext}"

        return super().format(**kw)
