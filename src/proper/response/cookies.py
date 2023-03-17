import re
import time
import warnings
from email.utils import formatdate
from http.cookies import Morsel, SimpleCookie
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Optional


class ResponseCookies(dict):
    """Response cookies.
    """

    def __setitem__(self, name: str, value: t.Any):
        self.set(name, value)

    def add(self, name: str, value: str):
        self.setdefault(name, []).append(value)

    def set(self, name: str, value: str):
        self[name] = [value]

    def get(self, name: str, default: t.Any = None) -> str:
        values = super().get(name)
        if values is None:
            return default
        return ", ".join(values)


class ResponseCookiesMixin:
    """Mixin with the methods related to the response cookies.
    """

    # Warn if a cookie header exceeds this size.
    # The default is 4093 and should be supported by most browsers
    # (See http://browsercookielimits.squawky.net)
    # A cookie larger than this size will still be sent, but it may be ignored or
    # handled incorrectly by some browsers. Set to 0 to disable this check.
    max_cookie_size: int = 4093

    # Set to True to not set cookies in this response, including any changes to the
    # session or CSRF token. You might want to use it for some read-only public
    # endpoints, like a RSS feed.
    disable_cookies: bool = False

    def __init__(self) -> None:
        self._cookies = ResponseCookies()

    def set_cookie(self, key: str, value: str = "", **kw) -> "Morsel":
        """
        Set (add) a cookie for the response. Returns the cookie set.

        Arguments are:

        - key:
            The cookie name.

        - value:
            The cookie value.

        - max_age:
            An integer representing a number of seconds, datetime.timedelta,
            or None. This value is used for the Max-Age and Expires values of
            the generated cookie (Expires will be set to now + max_age).
            If this value is None, the cookie will not have a Max-Age value.

        - path:
            A string representing the cookie Path value. It defaults to `/`.

        - domain:
            A string representing the cookie Domain, or None. If domain is None,
            no Domain value will be sent in the cookie.

        - secure:
            A boolean. If it's True, the secure flag will be sent in the cookie,
            if it's False, the secure flag will not be sent in the cookie.

        - httponly:
            A boolean. If it's True, the HttpOnly flag will be sent in the cookie,
            if it's False, the HttpOnly flag will not be sent in the cookie.

        - samesite:
            A string representing the SameSite attribute of the cookie or None.
            If samesite is None no SameSite value will be sent in the cookie.
            Should only be "Strict" or "Lax".
            https://www.owasp.org/index.php/SameSite

        - comment:
            A string representing the cookie Comment value, or None. If comment
            is None, no Comment value will be sent in the cookie.

        """
        return add_cookie(self.cookies, key, value, max_size=self.max_cookie_size, **kw)

    def unset_cookie(self, name: str) -> None:
        """
        Removes a cookie from this response (before sending it to the client).
        If the cookie is already on the client, use `set_delete_cookie()` instead.
        """
        if name in self.cookies:
            del self.cookies[name]

    def set_delete_cookie(self, name: str, *, path: str = "/", domain: str = "") -> None:
        """
        Delete a cookie from the client. Note that path and domain must match
        how the cookie was originally set.

        This sets the cookie to the empty string, and max_age=0 so that it should
        expire immediately.
        """
        self.set_cookie(name, value="", max_age=0, path=path, domain=domain)


RE_FILTER_FROM_COOKIE_NAME = re.compile(r"[^a-zA-Z0-9!*&#$%^'`+_~\.\-]*")
HOST_PREFIX = "__Host-"
SECURE_PREFIX = "__Secure-"


def add_cookie(
    cookies: CookiesDict,
    key: str,
    value="",
    *,
    max_age: "Optional[int]" = None,
    path="/",
    domain="",
    secure=False,
    httponly=False,
    samesite: "Optional[str]" = None,
    comment: "Optional[str]" = None,
    max_size: "Optional[int]" = None,
) -> Morsel:
    """Set (add) a cookie for the response.
    Returns the cookie set.

    Arguments are:

        cookies (CookieDict):
            The dict of cookies where the cookie will be added.

        key (str):
            The cookie name.

        value (str):
            The cookie value.

        max_age (int|None):
            An integer representing a number of seconds.
            This value is used for the Max-Age and Expires values of
            the generated cookie (Expires will be set to now + max_age).

        path (str):
            A string representing the cookie Path value. It defaults to `/`.
            The "/" character is interpreted as a directory separator and
            sub directories will be matched as well e.g.: `path="/docs"` will
            match "/docs/a", "/docs/a/b", etc.
            Therefore, `path="/"` wil match everything.

        domain (str):
            Specifies those hosts to which the cookie will be sent. If not specified,
            defaults to the host portion of the current document location
            (but not including subdomains).

            Contrary to earlier specifications, leading dots in domain names are
            ignored, so we don't need to add one. If a domain is specified,
            subdomains are always included.

        secure (bool):
            A "secure" cookie will only be sent to the server when a request is made
            using SSL and the HTTPS protocol. However, this doesn't mean that
            the cookie value is encrypted.

        httponly (bool):
            HTTP-only cookies aren't accessible via JavaScript through the
            `Document.cookie property`, the `XMLHttpRequest` API, or the `Request`
            API, to mitigate attacks against cross-site scripting (XSS).

        samesite (str):
            Allows servers to assert that a cookie ought not to be sent along with
            cross-site requests, which provides some protection against
            cross-site request forgery attacks.

            If set, should only be "Strict" or "Lax".

        comment (str|None):
            A string representing the cookie Comment value, or None. If comment
            is None, no Comment value will be sent in the cookie.

        max_size (int):
            Warn if a cookie header exceeds this size.
            The default is 4093 and should be supported by most browsers
            (see http://browsercookielimits.squawky.net).

            A cookie larger than this size will still be sent, but it may be
            ignored or handled incorrectly by some browsers. Set to 0 to disable
            this check.

    """
    key = re.sub(RE_FILTER_FROM_COOKIE_NAME, "", key)
    cookies[key] = value

    if max_age is not None:
        cookies[key]["max-age"] = max_age
        # Internet Explore (Edge too?) ignores "max-age" and requires "expires"
        cookies[key]["expires"] = formatdate(time.time() + max_age, usegmt=True)

    if key.startswith(HOST_PREFIX):
        path = "/"
    if path is not None:
        cookies[key]["path"] = path

    validate_domain(domain)

    if domain is not None and not key.startswith(HOST_PREFIX):
        cookies[key]["domain"] = domain

    if secure or key.startswith((SECURE_PREFIX, HOST_PREFIX)):
        cookies[key]["secure"] = True

    if httponly:
        cookies[key]["httponly"] = True

    if samesite:
        if str(samesite).lower() not in ("lax", "strict"):
            raise ValueError("`samesite` must be “lax” or “strict”.")
        cookies[key]["samesite"] = samesite

    if comment:
        cookies[key]["comment"] = comment

    if max_size is not None:
        validate_cookie_size(key, cookies[key].output(), max_size)

    return cookies[key]


def validate_domain(domain: str) -> None:
    if domain and "." not in domain:
        # Chrome doesn't allow names without a '.'
        # This should only come up with something like "localhost"
        warnings.warn(
            "For some browser, like Chrome, “{domain}” is not a valid cookie domain, "
            "because it must contain a “.”. Add an entry to your hosts file, "
            "for example “{domain}.localdomain”, and use that instead.",
            stacklevel=2,
        )


def validate_cookie_size(key: str, output: str, max_size: int) -> None:
    cookie_size = len(output)
    if cookie_size > max_size:
        warnings.warn(
            f"The “{key}” cookie is too large. The cookie final size "
            "is {cookie_size} bytes but the limit is {max_size} bytes. "
            "Browsers may silently ignore cookies larger than the limit.",
            stacklevel=2,
        )
