import ipaddress
import typing as t
from urllib.parse import unquote

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
from .helpers import DotDict, logger


if t.TYPE_CHECKING:
    from .core.request import Request
    from .core.response import Response


__all__ = (
    "head_to_get",
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


# STEP 1
def head_to_get(request: "Request", _response) -> None:
    """Transform a HEAD request to a fake GET request."""
    if request.request_method == HEAD:
        request.method = GET


# STEP 2
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


# STEP 3
def match(request: "Request", response) -> "Response | None":
    """Match the request url to a route."""
    host: str | None = request.host
    if host is not None and is_local_host(host):
        host = None
    router = request.app.router
    route, params = router.match(request.method, request.path, host)
    request.matched_route = route
    request.matched_params = params


# STEP 4
def redirect(request: "Request", response: "Response") -> "Response | None":
    """If a matched route is a redirect sets the header and response body
    for that redirect to happen and stop further process of the response.
    """
    route = request.matched_route
    if not route:
        return

    if route.redirect:
        params = request.matched_params or {}
        response.redirect_to(
            route.redirect.format(**params),
            status=route.redirect_status,
        )
        return response


# STEP 5
def copy_session(request: "Request", response: "Response"):
    """Get the session data from the cookie and puts into the request
    and response.
    """
    session = _find_session_by_cookie(request)
    if session is None:
        # No cookie, or a bad one: the request keeps the empty session it
        # was born with; the response gets a fresh one, since its flash
        # messages already wrote to the first. This is most requests.
        response.session = DotDict()
        return
    request.session = session
    response.session = session.copy()
    if FLASHES_SESSION_KEY in response.session:
        del response.session[FLASHES_SESSION_KEY]


def _find_session_by_cookie(request: "Request") -> DotDict | None:
    if SESSION_COOKIE_NAME not in request.cookies:
        return None
    session = request.get_signed_cookie(
        SESSION_COOKIE_NAME,
        salt=SESSION_COOKIE_SALT,
        max_age=request.app.config.SESSION_COOKIE_LIFETIME
    )
    logger.debug(">>> %s", session or "")
    # A session is a JSON object; any other signed value is no session
    return DotDict(session) if session and isinstance(session, dict) else None


# STEP 6
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


# STEP 7
def update_session_cookie(request: "Request", response: "Response") -> None:
    """Update the session cookie if the session was modified."""
    if response.session == request.session:
        return
    if response.session:
        _set_new_session_cookie(request, response)
    else:
        response.unset_cookie(SESSION_COOKIE_NAME)


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
