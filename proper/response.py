"""Response class.
"""
import json

from . import status
from .constants import FLASHES_SESSION_KEY
from .helpers import (
    add_cookie,
    CookiesDict,
    HeadersDict,
    tunnel_encode,
)


__all__ = ("Response", )


class Response:
    # Set to `True` by the dispatcher to indicate the endpoint was called.
    dispatched = False

    # Set it to `True` to stop the normal flow and return inmediatly.
    # Safety not guaranteed. I'm kidding, it was never guaranteed to begin with.
    stop = False

    # relative path of the template, minus the extension
    template = None

    # the default extension of the template.
    format = ".html"

    # Warn if a cookie header exceeds this size.
    # The default is 4093 and should be supported by most browsers
    # (See http://browsercookielimits.squawky.net)
    # A cookie larger than this size will still be sent, but it may be ignored or
    # handled incorrectly by some browsers. Set to 0 to disable this check.
    max_cookie_size = 4093

    error = None
    raw_body = None
    _content_type = "text/html"
    _charset = "utf-8"
    _session = None

    def __init__(
        self,
        status_code=status.ok,
        content_type="text/html",
        charset="utf-8"
    ):
        self.headers = HeadersDict()
        self.cookies = CookiesDict()
        self._session = {}

        self.status_code = status_code
        self.content_type = content_type
        self.charset = charset

    @property
    def body(self):
        return self.raw_body

    @body.setter
    def body(self, content):
        """Sets the response body content. If it is a dictionary,
        encodes it to JSON and sets the content_type to "application/json"
        """
        if isinstance(content, dict):
            self.set_json_body(content)
        else:
            self.set_raw_body(content)

    def set_raw_body(self, content):
        self.raw_body = content

    def set_json_body(self, content):
        self.content_type = "application/json"
        self.set_raw_body(json.dumps(content))

    @property
    def charset(self):
        return self._charset

    @charset.setter
    def charset(self, value):
        self._charset = value
        self.set_content_type_header()

    def set_content_type_header(self):
        header = f"{self._content_type}; charset={self._charset}"
        self.headers["Content-Type"] = header

    @property
    def content_type(self):
        return self._content_type

    @content_type.setter
    def content_type(self, value):
        self._content_type = value
        self.set_content_type_header()

    @property
    def has_body(self):
        return self.raw_body is not None

    @property
    def headers_items(self):
        return self.regular_headers_items + self.cookie_headers_items

    @property
    def regular_headers_items(self):
        return [
            (key, tunnel_encode(value, "utf-8"))
            for key, value in self.headers.items()
        ]

    @property
    def cookie_headers_items(self):
        return [
            tuple(morsel.output().split(": ", 1))
            for morsel in self.cookies.values()
        ]

    @property
    def session(self):
        """Read-only session"""
        return self._session

    @property
    def status_code(self):
        return self._status_code

    @status_code.setter
    def status_code(self, value):
        self._status_code = tunnel_encode(value)

    def flash(self, message, **data):
        """Flashes a message for the next request.
        To fetch the flashed message and to display it to the user,
        you must read `req.flashes` in the template.

        Requires an already fetched session.
        """
        flashes = self.session.get(FLASHES_SESSION_KEY, [])
        flashes.append((message, data))
        self.session[FLASHES_SESSION_KEY] = flashes

    def redirect_to(self, to, status_code=status.see_other, flash=None, **kwargs):
        self.status_code = status_code
        self.headers["location"] = to
        self.body = "\n".join(
            [
                "<!doctype html>",
                '<meta charset="utf-8">',
                f'<meta http-equiv="refresh" content="0; url={to}">',
                f'<script>window.location.href="{to}"</script>',
                "<title>Page Redirection</title>",
                "If you are not redirected automatically, follow the ",
                f'<a href="{to}">link to the page</a>.',
            ]
        )
        if flash:
            self.flash

    def set_cookie(self, key, value="", **kwargs):
        """Set (add) a cookie for the response. Returns the cookie set.

        Arguments are:

            key (str):
                The cookie name.

            value (str):
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
                Should only be "Strict" or "Lax".
                https://www.owasp.org/index.php/SameSite

            comment:
                A string representing the cookie Comment value, or None. If comment
                is None, no Comment value will be sent in the cookie.

        """
        return add_cookie(
            self.cookies, key, value, max_size=self.max_cookie_size, **kwargs
        )

    def unset_cookie(self, name):
        """Removes a cookie from this response (before sending it to the client).
        If the cookie is already on the client, use `delete_cookie()` instead.
        """
        if name in self.cookies:
            del self.cookies[name]

    def delete_cookie(self, name, *, path="/", domain=None):
        """Delete a cookie from the client. Note that path and domain must match
        how the cookie was originally set.

        This sets the cookie to the empty string, and max_age=0 so that it should
        expire immediately.
        """
        self.set_cookie(name, value="", max_age=0, path=path, domain=domain)

    def __call__(self, start_response):
        body = (self.raw_body or "").encode(self.charset)
        self.headers["Content-Length"] = str(len(body))

        start_response(self.status_code, self.headers_items)
        if not body:
            return []
        return [body]

    def __repr__(self):
        return f"<Response “{self._status_code}”>"
