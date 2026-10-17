import re
import time
import typing as t
import warnings
from email.utils import formatdate
from http.cookies import Morsel, SimpleCookie


HOST_PREFIX = "__Host-"
SECURE_PREFIX = "__Secure-"
RX_FILTER_FROM_COOKIE_NAME = re.compile(r"[^a-z0-9!*&#$%^'`+_~\.\-]*", re.IGNORECASE | re.UNICODE)
# The characters a cookie value can have as they are (RFC 6265, cookie-octet):
# not a space, a control character, `"`, `,`, `;` or `\`.
RX_COOKIE_VALUE = re.compile(r"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*")
_ENCODER = SimpleCookie()


def make_cookie(
    name: str,
    value: t.Any = "",
    *,
    max_age: int | None = None,
    path: str = "/",
    domain: str | None = None,
    secure: bool = False,
    httponly: bool = False,
    samesite: t.Literal["Lax", "Strict", "None"] | None = "Lax",
    comment: str = "",
) -> Morsel:
    """
    Makes a `Morsel` object representing a cookie.

    Arguments:
        name:
            The cookie name.
        value:
            The cookie value.
        max_age:
            An integer representing a number of seconds, datetime.timedelta,
            or None. This value is used for the Max-Age and Expires values of
            the generated cookie (Expires will be set to now + max_age).
            If this value is None, the cookie will not have a Max-Age value.
        path:
            A string representing the cookie Path value. It defaults to `/`.
        domain:
            A string representing the cookie Domain, or None. If domain is None,
            no Domain value will be sent in the cookie.
        secure:
            A boolean. If it's True, the secure flag will be sent in the cookie,
            if it's False, the secure flag will not be sent in the cookie.
        httponly:
            A boolean. If it's True, the HttpOnly flag will be sent in the cookie,
            if it's False, the HttpOnly flag will not be sent in the cookie.
        samesite:
            A string representing the SameSite attribute of the cookie or None.
            If samesite is Python `None`, no SameSite value will be sent.
            Should be `"Lax"`, `"Strict"`, `"None"`, or Python `None`.
            See: https://www.owasp.org/index.php/SameSite

            **Note**: Modern browsers place restriction on cookies without the
            "same-site" cookie attribute set. To that end this attribute
            is set to `"Lax"` by default.
        comment:
            A string representing the cookie Comment value, or None. If comment
            is None, no Comment value will be sent in the cookie.

    """
    cookie = Morsel()
    name = RX_FILTER_FROM_COOKIE_NAME.sub("", name)
    if isinstance(value, bytes):
        value = value.decode("utf8")
    value = str(value)
    if RX_COOKIE_VALUE.fullmatch(value):
        coded = value
    else:
        # quoted, as the request reads it back: a `;` in the value can't
        # add an attribute to the cookie
        coded = _ENCODER.value_encode(value)[1]
    cookie.set(name, value, coded)

    if max_age is not None:
        cookie["max-age"] = max_age
        # Internet Explorer (Edge too?) ignores "max-age" and requires "expires"
        cookie["expires"] = formatdate(timeval=time.time() + max_age, usegmt=True)

    if name.startswith(HOST_PREFIX):
        path = "/"
    if path is not None:
        cookie["path"] = path

    if domain is not None and not name.startswith(HOST_PREFIX):
        validate_domain(domain)
        cookie["domain"] = domain

    if secure or name.startswith((SECURE_PREFIX, HOST_PREFIX)):
        cookie["secure"] = True

    if httponly:
        cookie["httponly"] = True

    if samesite:
        if str(samesite).lower() not in ("lax", "strict", "none"):
            raise ValueError('`samesite` must be `"Lax"`, `"Strict"`, `"None"`, or `None`')
        cookie["samesite"] = samesite

    cookie["comment"] = comment

    return cookie


def validate_domain(domain: str | None) -> None:
    if domain and "." not in domain:
        # Chrome doesn't allow names without a '.'
        # This should only come up with something like "localhost"
        warnings.warn(
            f"For some browser, like Chrome, \u201c{domain}\u201d is not a valid cookie domain, "
            f"because it must contain a \u201c.\u201d. Add an entry to your hosts file, "
            f"for example \u201c{domain}.localdomain\u201d, and use that instead.",
            stacklevel=2,
        )


def validate_cookie_size(name: str, output: str, max_size: int) -> None:
    cookie_size = len(output)
    if cookie_size > max_size:
        warnings.warn(
            f"The \u201c{name}\u201d cookie is too large. The cookie final size "
            f"is {cookie_size} bytes but the limit is {max_size} bytes. "
            f"Browsers may silently ignore cookies larger than the limit.",
            stacklevel=2,
        )
