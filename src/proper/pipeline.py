import copy
import ipaddress
import typing as t
from urllib.parse import quote, unquote

from . import status
from .constants import (
    DELETE,
    FLASHES_SESSION_KEY,
    GET,
    HEAD,
    PATCH,
    POST,
    PUT,
    QUERY,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SALT,
)
from .controller import Controller
from .core.config import parse_trusted_hosts
from .helpers import logger


if t.TYPE_CHECKING:
    from .app import App
    from .core.request import Request
    from .core.response import Response


__all__ = (
    "check_host",
    "head_to_get",
    "host_is_trusted",
    "is_local_host",
    "method_override",
    "match",
    "redirect",
    "copy_session",
    "dispatch",
    "update_session_cookie",
)

TController = type[Controller]
LOCAL_HOSTS = ("localhost", "0.0.0.0", "127.0.0.1", "::", "::1")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_OCTAL_DIGITS = frozenset("01234567")
_DECIMAL_DIGITS = frozenset("0123456789")


def is_local_host(host: str) -> bool:
    """Is `host` (as in `request.host`: lowercase, without the port and the
    brackets of an IPv6 address) a name of this machine?

    It is when, after its percent-escapes are decoded, it is `localhost` or
    an IPv4 address in 127.0.0.0/8 or 0.0.0.0, with or without one
    trailing dot, or the IPv6 address `::1` or `::`, or one of those IPv4
    addresses mapped to IPv6 (`::ffff:127.0.0.1`). An IPv4 address is read
    as browsers read the host of a URL (the WHATWG URL Standard), so
    `127.1`, `127.000.000.001`, `0x7f.0.0.1`, `0177.0.0.1` and
    `2130706433` are all 127.0.0.1.
    """
    if host in LOCAL_HOSTS:
        return True
    if "%" in host:
        host = unquote(host).lower()
    if ":" in host:
        try:
            address = ipaddress.IPv6Address(host)
        except ValueError:
            return False
        mapped = address.ipv4_mapped
        if mapped is not None:
            return mapped.is_loopback or mapped.is_unspecified
        return address.is_loopback or address.is_unspecified
    host = host.removesuffix(".")
    if host == "localhost":
        return True
    number = _ipv4_number(host)
    return number is not None and (number >> 24 == 127 or number == 0)


def _ipv4_number(host: str) -> int | None:
    """The IPv4 address `host` is, as a number, or `None` if it is not one.

    As the IPv4 parser of the WHATWG URL Standard: one to four parts
    joined by dots, each decimal, octal (with a leading `0`) or hex (with
    `0x`); the last part fills the bytes the others leave.
    """
    parts = host.split(".")
    if len(parts) > 4:
        return None
    numbers = []
    for part in parts:
        if part[:2] in ("0x", "0X"):
            digits, base, allowed = part[2:], 16, _HEX_DIGITS
        elif len(part) > 1 and part[0] == "0":
            digits, base, allowed = part[1:], 8, _OCTAL_DIGITS
        elif part:
            digits, base, allowed = part, 10, _DECIMAL_DIGITS
        else:
            return None
        if not allowed.issuperset(digits):
            return None
        # 12 digits are at least 8 ** 11 = 2 ** 33 in any of the three
        # bases, more than any part can be, and `int` raises `ValueError`
        # for a decimal text longer than 4300 digits.
        digits = digits.lstrip("0")
        if len(digits) > 11:
            return None
        numbers.append(int(digits, base) if digits else 0)
    *first, last = numbers
    if any(n > 255 for n in first) or last >= 256 ** (5 - len(numbers)):
        return None
    number = last
    for index, n in enumerate(first):
        number += n << (8 * (3 - index))
    return number


# How many hosts found to be trusted are remembered, so the next request
# with one of them is a single lookup. A wildcard (`.example.com`, or a
# route with a host placeholder) trusts more names than anyone should keep.
MAX_KNOWN_HOSTS = 1024


class TrustedHosts:
    """The hosts an app answers to, from its config and its routes as they
    are now. See `host_is_trusted`."""

    __slots__ = ("host", "listed", "n_routes", "any", "suffixes", "routes", "known")

    def __init__(self, app: "App") -> None:
        config = app.config
        routes = app.router.routes
        # What this was made from, to make it again when one changes
        self.host = config.HOST
        self.listed = config.TRUSTED_HOSTS
        self.n_routes = len(routes)

        listed = parse_trusted_hosts(self.listed)
        self.any = "*" in listed
        self.suffixes = tuple(name for name in listed if name[0] == ".")
        names = {name.removeprefix(".") for name in listed}
        # `HOST` may have a port: `example.com:8080`, `[::1]:2300`
        host = str(self.host).strip().lower()
        if host and host[0] != "[":
            names.add(host.partition(":")[0].removesuffix("."))
        # One route for each host pattern
        patterns = {
            route.host: route
            for route in routes
            if route.host_re is not None and not route.build_only
        }
        self.routes = tuple(patterns.values())
        self.known = names

    def check(self, host: str) -> bool:
        name = host.removesuffix(".")
        trusted = (
            self.any
            or name in self.known
            or "." not in name
            or name.endswith(".localhost")
            or is_local_host(host)
            or _is_ip_address(name)
            or name.endswith(self.suffixes)
            or any(route.match_host(name) is not None for route in self.routes)
        )
        if trusted and len(self.known) < MAX_KNOWN_HOSTS:
            self.known.add(host)
        return trusted


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def host_is_trusted(app: "App", host: str) -> bool:
    """Is `host` (as in `request.host`: lowercase, without the port and the
    brackets of an IPv6 address) one this app answers to?

    A page of another site can't read the answers of your app, unless its
    own domain is made to point at your server (DNS rebinding): then the
    browser takes both for the same site. Its requests still carry the
    other domain in `Host`, so the app refuses the names it doesn't know.

    Trusted, with or without one trailing dot:

    - an IP address: only a name can be made to point somewhere else;
    - a name without a dot (`web`, `myapp-web-1`), as containers call each
      other: no domain anyone can register is one;
    - a name of this machine (`is_local_host`), or one under `.localhost`,
      which browsers never look up;
    - the name in the `HOST` setting;
    - the names in the `TRUSTED_HOSTS` setting: `www.example.com` is that
      name, `.example.com` is `example.com` and every name under it, and
      `*` is any name;
    - a name that matches the `host` of a route.
    """
    trusted = app._trusted_hosts
    if (
        trusted is None
        or trusted.host is not app.config.HOST
        or trusted.listed is not app.config.TRUSTED_HOSTS
        or trusted.n_routes != len(app.router.routes)
    ):
        trusted = app._trusted_hosts = TrustedHosts(app)
    return host in trusted.known or trusted.check(host)


UNTRUSTED_HOST = (
    "Bad Request: the host of this request is not one this application "
    "answers to. If it should be, add it to TRUSTED_HOSTS in the config.\n"
)


# STEP 1
def check_host(request: "Request", response: "Response") -> "Response | None":
    """Refuse a request for a host the app doesn't know (see
    `host_is_trusted`) with a `400 Bad Request`.

    A request without a `Host` header is not from a browser, and goes on.
    The answer is a line of text, not an error page: in `DEBUG` that page
    shows the code and the config.
    """
    if host_is_trusted(request.app, request.host):
        return None
    if not request.headers.get("host"):
        return None
    logger.warning(
        "Untrusted host %r: add it to TRUSTED_HOSTS if the app should answer to it.",
        request.host[:255],
    )
    response.status = status.bad_request
    response.content_type = "text/plain"
    response.body = UNTRUSTED_HOST
    return response


# STEP 2
def head_to_get(request: "Request", _response) -> None:
    """Transform a HEAD request to a fake GET request."""
    if request.request_method == HEAD:
        request.method = GET


# STEP 3
def method_override(request: "Request", _response) -> None:
    """Overrides the request's `POST` method with the method defined in
    the `X-HTTP-Method-Override` header or the `_method` parameter in the
    path or in the request body.

    The `POST` method can be overridden only by these HTTP methods:
    * `PUT`
    * `PATCH`
    * `DELETE`
    * `QUERY`

    """
    # Only override the method if the original method is POST
    if request.method != POST:
        return

    new_method = request.headers.get("x-http-method-override")
    if not new_method:
        new_method = request.query.get("_method") or request.form.get("_method")

    new_method = (new_method or "").upper()
    if new_method not in (PUT, PATCH, DELETE, QUERY):
        return

    request.method = new_method


# STEP 4
def match(request: "Request", response) -> "Response | None":
    """Match the request url to a route."""
    host: str | None = request.host
    if host is not None and is_local_host(host):
        host = None
    router = request.app.router
    route, params = router.match(request.method, request.path, host)
    request.matched_route = route
    request.matched_params = params


# STEP 5
def redirect(request: "Request", response: "Response") -> "Response | None":
    """If a matched route is a redirect sets the header and response body
    for that redirect to happen and stop further process of the response.
    """
    route = request.matched_route
    if not route:
        return

    if route.redirect:
        # the values were decoded from the path: encoded again for the URL
        params = {
            name: quote(str(value), safe="/:@!$&'()*+,;=~")
            for name, value in (request.matched_params or {}).items()
        }
        response.redirect_to(
            route.redirect.format(**params),
            status=route.redirect_status,
        )
        return response


# STEP 6
def copy_session(request: "Request", response: "Response"):
    """Get the session data from the cookie and puts into the request
    and response.
    """
    session = _find_session_by_cookie(request)
    if session is None:
        # No cookie, or a bad one: the request and the response keep the
        # empty sessions they were born with. This is most requests.
        return
    request.session = session
    response.session = _copy_session(session)


# Values that can't change, shared by the two sessions
_IMMUTABLE = frozenset({str, int, float, bool, bytes, type(None)})


def _copy_session(session: dict) -> dict:
    """The response's session: the request's, without the flashed messages
    (they are shown once), and with a copy of every value that can change.

    `update_session_cookie` compares the two to know if the session
    changed. A list or a dict they shared would change in both, and the
    change wouldn't be saved.
    """
    return {
        key: value if type(value) in _IMMUTABLE else copy.deepcopy(value)
        for key, value in session.items()
        if key != FLASHES_SESSION_KEY
    }


def _find_session_by_cookie(request: "Request") -> dict | None:
    if SESSION_COOKIE_NAME not in request.cookies:
        return None
    session = request.get_signed_cookie(
        SESSION_COOKIE_NAME,
        salt=SESSION_COOKIE_SALT,
        max_age=request.app.config.SESSION_COOKIE_LIFETIME
    )
    logger.debug(">>> %s", session or "")
    # A session is a JSON object; any other signed value is no session
    return session if session and type(session) is dict else None


# STEP 7
def dispatch(request: "Request", response: "Response") -> "Response | None":
    route = request.matched_route
    assert route
    assert route.to
    Controller, action_name = route.resolve()
    request.matched_action = action_name

    # We instantiate the view class so we can have an independent
    # container for this request.
    co = Controller(request, response)
    co._dispatch(action_name)


# STEP 8
def update_session_cookie(request: "Request", response: "Response") -> None:
    """Update the session cookie if the session was modified."""
    if response.session == request.session:
        return
    if response.session:
        _set_new_session_cookie(request, response)
    else:
        config = request.app.config
        response.unset_cookie(
            SESSION_COOKIE_NAME,
            path=config.SESSION_COOKIE_PATH or "/",
            domain=config.SESSION_COOKIE_DOMAIN,
        )


def _set_new_session_cookie(request: "Request", response: "Response") -> None:
    config = request.app.config
    response.set_signed_cookie(
        SESSION_COOKIE_NAME,
        dict(response.session),
        salt=SESSION_COOKIE_SALT,
        max_age=int(config.SESSION_COOKIE_LIFETIME)
        if config.SESSION_COOKIE_LIFETIME
        else None,
        httponly=config.SESSION_COOKIE_HTTPONLY,
        domain=config.SESSION_COOKIE_DOMAIN,
        path=config.SESSION_COOKIE_PATH or "/",
        secure=request.is_secure,
        samesite=config.SESSION_COOKIE_SAMESITE,
    )
