import re
import time
import warnings
from email.utils import formatdate
from http.cookies import Morsel, SimpleCookie


__all__ = ("CookiesDict", "add_cookie", )


# Monkey-patching the Morsel to add support for samesite for Python version < 3.8
# https://github.com/python/cpython/pull/6413
Morsel._reserved["samesite"] = "SameSite"


class CookiesDict(SimpleCookie):
    pass


RE_FILTER_FROM_COOKIE_NAME = re.compile(r"[^a-zA-Z0-9!*&#$%^'`+_~\.\-]*")
HOST_PREFIX = "__Host-"
SECURE_PREFIX = "__Secure-"


def add_cookie(
    cookies,
    key,
    value="",
    *,
    max_age=None,
    path="/",
    domain=None,
    secure=False,
    httponly=False,
    samesite=None,
    comment=None,
    max_size=None,
):
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

        domain (str|None):
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
            cross-site request forgery attacks (CSRF).

            Should only be "Strict" or "Lax".

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

    validate_cookie_size(key, cookies[key].output(), max_size)
    return cookies[key]


def validate_domain(domain):
    if domain and "." not in domain:
        # Chrome doesn't allow names without a '.'
        # This should only come up with something like "localhost"
        warnings.warn(
            "For some browser, like Chrome, “{domain}” is not a valid cookie domain, "
            "because it must contain a “.”. Add an entry to your hosts file, "
            "for example “{domain}.localdomain”, and use that instead.",
            stacklevel=2,
        )


def validate_cookie_size(key, output, max_size):
    cookie_size = len(output)
    if cookie_size > max_size:
        warnings.warn(
            f"The “{key}” cookie is too large. The cookie final size "
            "is {cookie_size} bytes but the limit is {max_size} bytes. "
            "Browsers may silently ignore cookies larger than the limit.",
            stacklevel=2,
        )
