"""
Utilities to declare routes in your application.

"""

import os
import re
import typing as t
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote, urlencode

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
from ..helpers import import_string
from ..types import Iterable, THandler
from .matcher import LinearPattern, linear_pattern


__all__ = (
    "FORMATS",
    "HOST_SAFE",
    "Route",
    "StaticRoute",
)

"""Characters `url_for` doesn't percent-encode in a placeholder value, besides
the unreserved ones: `/` and the rest of the characters that RFC 3986 allows
in a path segment (`pchar`), without `%`.
"""
PATH_SAFE = "/:@!$&'()*+,;="

"""Characters `url_for` doesn't percent-encode in the `#fragment`, besides
the unreserved ones: those of `PATH_SAFE` and `?` (RFC 3986 §3.5).
"""
FRAGMENT_SAFE = PATH_SAFE + "?"

"""Characters `url_for` accepts in a host placeholder value: the unreserved
characters of RFC 3986 (letters, digits, `-._~`). They are the characters of
a host name (RFC 1123: letters, digits and `-`, in labels joined by `.`),
plus `_` and `~`, which a reg-name (RFC 3986 §3.2.2) allows as they are. A
reg-name's sub-delims (`!$&'()*+,;=`) and percent-escapes are left out: no
host name has them.
"""
HOST_SAFE = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)

DOT_SEGMENTS = (".", "..")

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

"""A host longer than this matches no route with a host. A DNS name has at
most 253 characters (RFC 1035 §2.3.4: 255 bytes on the wire), 254 with a
trailing dot. The limit shortens the text `re` reads for a host pattern
with a custom format, but does not bound that time, which depends on the
format."""
MAX_HOST_LENGTH = 255


def _compile_pattern(
    pattern: str, *, anchor_suffix: str = ""
) -> tuple[re.Pattern, str, dict, dict, list, LinearPattern | None]:
    """Compile a placeholder-aware pattern (path or host).

    Returns a 6-tuple of:

    - the compiled regex (with named groups for each placeholder),
    - a "plain" string with `:name` markers preserved, for reading,
    - a dict of placeholder name → regex source,
    - a dict of placeholder name → type caster (only for `int`/`float`),
    - the pieces to build a URL from: a list of `(literal, name)` pairs,
      where `name` is `None` for the text after the last placeholder,
    - a `LinearPattern` that matches as the regex does without
      backtracking, or `None` when the regex is used (see
      `matcher.linear_pattern`).
    """
    parts: list[str] = []
    parts_re: list[str] = []
    pieces: list[tuple[str, str | None]] = []
    placeholders: dict = {}
    formats: dict = {}
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
        pieces.append((part, match.group(1)))

        name, fmt = match.groups()
        if name in placeholders:
            raise DuplicatedRoutePlaceholder(name, pattern)

        if fmt == "int":
            casters[name] = int
        elif fmt == "float":
            casters[name] = float

        rx = FORMATS.get(fmt, fmt)
        placeholders[name] = rx
        formats[name] = fmt
        parts.append(f":{name}")
        parts_re.append(rf"(?P<{name}>{rx})")

    tail = pattern[index:]
    if tail:
        parts.append(tail)
        parts_re.append(re.escape(tail))
        pieces.append((tail, None))

    str_re = r"".join(parts_re) + anchor_suffix
    try:
        compiled = re.compile(str_re)
    except Exception as e:
        raise BadRouteFormat(e) from e

    linear = linear_pattern(pieces, formats, anchor_suffix, compiled)
    return compiled, "".join(parts), placeholders, casters, pieces, linear


def _build(pieces: "list[tuple[str, str | None]]", values: dict) -> str:
    """Join the pieces from `_compile_pattern`, with each placeholder
    replaced by its value. The literal text is copied as it is in the
    pieces, so it follows the same placeholder grammar as matching."""
    return "".join(
        literal if name is None else literal + values[name] for literal, name in pieces
    )


def _dot_segment_placeholder(
    pieces: "list[tuple[str, str | None]]", values: dict
) -> str | None:
    """The name of a placeholder whose value is part of a `.` or `..`
    segment of the path built from `pieces`, or `None`.

    Clients remove those segments, with the one before a `..` (RFC 3986
    §5.2.4), so such a URL doesn't lead to the route.
    """
    # Fast path: such a value has a part between slashes made only of dots.
    if not any(
        part and part.strip(".") == ""
        for value in values.values()
        for part in value.split("/")
    ):
        return None

    spans = []
    pos = 0
    for literal, name in pieces:
        pos += len(literal)
        if name is not None:
            spans.append((pos, pos + len(values[name]), name))
            pos += len(values[name])

    start = 0
    for segment in _build(pieces, values).split("/"):
        end = start + len(segment)
        if segment in DOT_SEGMENTS:
            for span_start, span_end, name in spans:
                if span_start < end and start < span_end:
                    return name
        start = end + 1
    return None


def has_dot_segment(path: str) -> bool:
    """Does `path` have a `.` or `..` segment?"""
    return "/." in path and any(segment in DOT_SEGMENTS for segment in path.split("/"))


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
        controller:
            Optional. The controller class that `to` is routed on, when it is
            not the class that defines the method: `to` may be an action that
            the class inherits, and a function doesn't know the class it was
            read from (`ArticleController.index` is the same function as
            `ApplicationController.index` when `ArticleController` inherits
            it). The request then runs on an instance of this class, with its
            callbacks, and `controller_prefix` is made from its name. Without
            it, the class that defines the method is used. `resource()`
            passes it; the name of the route is not changed by it.

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
        controller: type | None = None,
    ) -> None:
        self.name = name
        self.host = host
        self.redirect = redirect
        self.redirect_status = redirect_status
        self.defaults = defaults or {}

        self.method = method
        self.path = path
        self._resolved: "tuple[type, str] | None" = None
        self._controller_prefix: str | None = None
        self._controller = controller
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
        self._resolved = None
        self._controller_prefix = None
        if not self.name and value:
            cls, method = value.__qualname__.rsplit(".", 1)
            prefix = _namespace_prefix(getattr(value, "__module__", "") or "")
            self.name = f"{prefix}{cls.removesuffix('Controller')}.{method}"

    @property
    def controller(self) -> type | None:
        """The controller class given to the route (see `Route`), or `None`
        when the class that defines `to` is used."""
        return self._controller

    @property
    def controller_prefix(self) -> str:
        """The snake-cased controller name of `to` plus `_`, so that for
        `ItemController.show` the placeholder `:item_id` can also be read as
        `id` from an object. Empty without a `to`. The controller is the
        route's `controller` if it has one, else the class that defines
        `to`."""
        prefix = self._controller_prefix
        if prefix is None:
            if self._to:
                if self._controller is not None:
                    cname = self._controller.__name__
                else:
                    cname = self._to.__qualname__.split(".")[0]
                cname = cname.removesuffix("Controller")
                prefix = inflection.underscore(cname) + "_"
            else:
                prefix = ""
            self._controller_prefix = prefix
        return prefix

    def resolve(self) -> "tuple[type, str]":
        """The controller class and action name behind `to`, looked up once,
        on the first request, and kept for the next ones. The class is the
        route's `controller` if it has one; otherwise it is the class that
        defines `to`, imported from the function's module."""
        if self._resolved is None:
            assert self._to
            cls_name, action_name = self._to.__qualname__.rsplit(".", 1)
            if self._controller is not None:
                self._resolved = (self._controller, action_name)
            else:
                module = import_string(self._to.__module__)
                self._resolved = (getattr(module, cls_name), action_name)
        return self._resolved

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
            "controller",
        ):
            if not hasattr(other, attr) or getattr(self, attr) != getattr(other, attr):
                return False
        return True

    @property
    def path_backtracks(self) -> bool:
        """Could `re` backtrack on the path, so that it is matched with a
        `matcher.LinearPattern` (see `matcher.linear_pattern`)? Such a
        route can't be combined with others in one regex."""
        return self._path_linear is not None

    @property
    def build_only(self) -> bool:
        """Is this a route only for `url_for()`
        and not for matching?"""
        return not (self.to or self.redirect)

    def match(self, path: str) -> dict | None:
        """The parameters of `path` if it matches this route, or `None`.

        A path where a placeholder's value is part of a `.` or `..` segment
        (`/files/..` for `/files/:name`) doesn't match: `format` can't
        build a URL with that value, because clients remove those segments.
        """
        assert self.path_re
        if self._path_linear is not None:
            params = self._path_linear.match(path)
            if params is None:
                return None
        else:
            m = self.path_re.match(path)
            if m is None:
                return None
            params = m.groupdict()
        if has_dot_segment(path) and _dot_segment_placeholder(
            self._raw_path_pieces,
            {name: params[name] for name in self.path_placeholders},
        ):
            return None
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

        A host longer than `MAX_HOST_LENGTH` (255) characters matches no
        host pattern: no host name is that long.
        """
        if self.host_re is None:
            return {}
        if host is None or len(host) > MAX_HOST_LENGTH:
            return None
        if self._host_linear is not None:
            params = self._host_linear.match(host)
            if params is None:
                return None
        else:
            m = self.host_re.match(host)
            if m is None:
                return None
            params = m.groupdict()
        for name, caster in self.host_casters.items():
            if name in params:
                params[name] = caster(params[name])
        return params

    def format(self, **kw) -> str:
        """Build the URL path of this route, with the placeholders filled
        with the values in `kw`.

        Each value must match its placeholder's format as a whole. The values,
        and the text of the route around them, are percent-encoded, except
        for the characters a path can have as they are (`PATH_SAFE`): a `/`,
        which only a placeholder whose format matches a `/` (such as `path`)
        accepts, and `:@!$&'()*+,;=`, so a value like `":signed_id"` stays as
        written. The arguments that are not placeholders become the query
        string, percent-encoded as a form (`urlencode`).

        A value that would make a `.` or `..` segment of the path (`"."` or
        `".."` for `/files/:name`, or `"a/../b"` for a `<path>`) raises
        `BadRoutePlaceholder`: browsers and HTTP clients remove those
        segments, with the one before a `..` (RFC 3986 §5.2.4), so the URL
        would lead to another page. Percent-encoding them doesn't help:
        `%2e` is a dot to them too.
        """
        path_params = self._get_path_params(kw)
        values = {
            name: quote(value, safe=PATH_SAFE) for name, value in path_params.items()
        }
        name = _dot_segment_placeholder(self._path_pieces, values)
        if name is not None:
            raise BadRoutePlaceholder(
                name,
                self.path,
                self._path_placeholder_re[name].pattern,
                reason="would make a `.` or `..` segment, which clients remove",
            )
        url = _build(self._path_pieces, values) or "/"

        query_params = self._get_query_params(path_params, kw)
        if query_params:
            url = url + "?" + urlencode(query_params)

        return url

    def format_host(self, **kw) -> str | None:
        """Build the host string for this route, substituting placeholders.

        Each value must match its placeholder's format as a whole and have
        only letters, digits and `-._~` (`HOST_SAFE`), or `BadRoutePlaceholder`
        is raised: the value is not encoded, so `"evil.com?"` would make the
        host `evil.com`.

        Returns `None` if the route has no host constraint.
        """
        if self._host_pieces is None:
            return None
        host_params = self._get_host_params(kw)
        for name, value in host_params.items():
            if not HOST_SAFE.issuperset(value):
                raise BadRoutePlaceholder(
                    name,
                    self.host or "",
                    self._host_placeholder_re[name].pattern,
                    reason=(
                        "has a character that a host name can't have "
                        "(only letters, digits and -._~)"
                    ),
                )
        return _build(self._host_pieces, host_params)

    # Private

    def _compile_path(self) -> None:
        path_re, path_plain, placeholders, casters, pieces, linear = _compile_pattern(
            self.path, anchor_suffix=r"/?$"
        )
        self.path_re = path_re
        self._path_linear = linear
        self.path_plain = path_plain
        self.path_placeholders = placeholders
        self.path_casters = casters
        # What `format` needs, ready: the pieces of the path, with the text
        # percent-encoded as the values are (a route is matched against the
        # decoded path), and one compiled regex per placeholder to validate
        # its value.
        self._raw_path_pieces = pieces
        self._path_pieces = [
            (quote(literal, safe=PATH_SAFE), name) for literal, name in pieces
        ]
        self._path_placeholder_re = {
            name: re.compile(rx) for name, rx in placeholders.items()
        }

    def _compile_host(self) -> None:
        if self._host is None:
            self.host_re = None
            self.host_plain = None
            self.host_placeholders = {}
            self.host_casters = {}
            self._host_pieces = None
            self._host_placeholder_re = {}
            self._host_linear = None
            return
        host_re, host_plain, placeholders, casters, pieces, linear = _compile_pattern(
            self._host, anchor_suffix=r"$"
        )
        self.host_re = host_re
        self._host_linear = linear
        self.host_plain = host_plain
        self.host_placeholders = placeholders
        self.host_casters = casters
        self._host_pieces = pieces
        self._host_placeholder_re = {
            name: re.compile(rx) for name, rx in placeholders.items()
        }

    def _get_path_params(self, kwargs: dict) -> dict:
        return self._get_pattern_params(
            self._path_placeholder_re, kwargs, source=self.path
        )

    def _get_host_params(self, kwargs: dict) -> dict:
        return self._get_pattern_params(
            self._host_placeholder_re, kwargs, source=self.host or ""
        )

    @staticmethod
    def _get_pattern_params(
        placeholders: "dict[str, re.Pattern]", kwargs: dict, *, source: str
    ) -> dict:
        params = {}
        for name, rx in placeholders.items():
            value = kwargs.get(name)
            if value is None:
                raise MissingRouteParameter(name, source)
            value = str(value)
            if not rx.fullmatch(value):
                raise BadRoutePlaceholder(name, source, rx.pattern)
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
