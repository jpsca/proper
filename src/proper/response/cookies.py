import re
import time
import typing as t
import warnings
from email.utils import formatdate
from http.cookies import Morsel

from proper.core.global_context import current
from proper.helpers import tunnel_encode


RE_FILTER_FROM_COOKIE_NAME = re.compile(r"[^a-zA-Z0-9!*&#$%^'`+_~\.\-]*")
HOST_PREFIX = "__Host-"
SECURE_PREFIX = "__Secure-"


class ResponseCookiesMixin:
    """Mixin with the methods related to the response cookies."""

    cookies: dict[str, Morsel]

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
        self.cookies = {}
        super().__init__()

    def set_cookie(
        self,
        name: str,
        value: t.Any = "",
        *,
        max_age: int | None = None,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: t.Literal["Lax"] | t.Literal["Strict"] | None = "Lax",
        comment: str = "",
        signed: bool = False,
        salt: str = "",
    ) -> None:
        """
        Set (add) a cookie to the response.

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
                If samesite is None no SameSite value will be sent in the cookie.
                Should only be `"Lax"`, `"Strict"`, or `None`.
                See: https://www.owasp.org/index.php/SameSite

                **Note**: Modern browsers place restriction on cookies without the
                "same-site" cookie attribute set. To that end this attribute
                is set to `"Lax"` by default.


            comment:
                A string representing the cookie Comment value, or None. If comment
                is None, no Comment value will be sent in the cookie.

            signed:
                Cryptographically sign the cookie before setting it.
                Default is `False`.

            salt:
                optional salt argument for added key strength, but you will
                need to remember to pass it to the corresponding
                `request.get_signed_cookie()` call.

        """
        name = re.sub(RE_FILTER_FROM_COOKIE_NAME, "", name)
        cookie = self.cookies[name] = Morsel()

        if signed:
            assert current.app
            serializer = current.app.get_serializer(salt)
            value = serializer.dumps(value)
        else:
            if not isinstance(value, (str, bytes)):
                value = str(value)

        if isinstance(value, bytes):
            value = value.decode("utf8")
        else:
            value = str(value)

        cookie.set(name, value, value)

        if max_age is not None:
            cookie["max-age"] = max_age
            # Internet Explore (Edge too?) ignores "max-age" and requires "expires"
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
            if str(samesite).lower() not in ("lax", "strict"):
                raise ValueError('`samesite` must be `"Lax"`, `"Strict"` or `None`')
            cookie["samesite"] = samesite

        cookie["comment"] = comment

        if self.max_cookie_size > 0:
            validate_cookie_size(name, cookie.output(), self.max_cookie_size)

        self.cookies[name] = cookie

    def unset_cookie(self, name: str) -> None:
        """Unset a cookie in the response.

        Clears the contents of the cookie, **and instructs the user agent to
        immediately expire its own copy of the cookie**.

        Arguments:

            name:
                The cookie name.
        """
        self.set_cookie(name, value=" ", max_age=0, comment="")

    def set_signed_cookie(
        self,
        name: str,
        value: t.Any = "",
        *,
        max_age: int | None = None,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: t.Literal["Lax"] | t.Literal["Strict"] | None = "Lax",
        comment: str = "",
        salt: str = "",
    ) -> None:
        """A shorthand for `.set_cookie(..., signed=True)`"""
        return self.set_cookie(
            name=name,
            value=value,
            max_age=max_age,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
            comment=comment,
            signed=True,
            salt=salt,
        )

    def _get_cookie_tuples(self) -> list[tuple[str, str]]:
        if self.disable_cookies or not self.cookies:
            return []

        values = [morsel.OutputString() for morsel in self.cookies.values()]
        return [(
            "Set-Cookie",
            tunnel_encode(", ".join(values))
        )]


def validate_domain(domain: str | None) -> None:
    if domain and "." not in domain:
        # Chrome doesn't allow names without a '.'
        # This should only come up with something like "localhost"
        warnings.warn(
            "For some browser, like Chrome, “{domain}” is not a valid cookie domain, "
            "because it must contain a “.”. Add an entry to your hosts file, "
            "for example “{domain}.localdomain”, and use that instead.",
            stacklevel=2,
        )


def validate_cookie_size(name: str, output: str, max_size: int) -> None:
    cookie_size = len(output)
    if cookie_size > max_size:
        warnings.warn(
            f"The “{name}” cookie is too large. The cookie final size "
            "is {cookie_size} bytes but the limit is {max_size} bytes. "
            "Browsers may silently ignore cookies larger than the limit.",
            stacklevel=2,
        )
