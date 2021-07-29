"""
Response class.
"""
import json
from datetime import date
from hashlib import md5
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)
from uuid import uuid4

from . import status
from .constants import FLASHES_SESSION_KEY
from .helpers import (
    CookiesDict,
    HeadersDict,
    add_cookie,
    iterable,
    tunnel_encode,
)
from .request import Request


__all__ = ("Response",)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class Response:
    # Set to `True` by the dispatcher to indicate the endpoint was called.
    dispatched: bool = False

    # Set it to `True` to stop the normal flow and return inmediatly.
    # Safety not guaranteed. I'm kidding, it was never guaranteed to begin with.
    stop: bool = False

    # relative path of the template, minus the extension
    template: Optional[str] = None

    # the default extension of the template.
    format: str = ".html"

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

    error: Optional[Exception] = None
    raw_body: Optional[str] = None

    _app: Any
    _req: Optional[Request]
    _session: Dict[str, str]
    _etag: Optional[str] = None
    _last_modified: Optional[date] = None

    def __init__(
        self,
        status_code: str = status.ok,
        content_type: str = "text/html",
        charset: str = "utf-8",
        _app: Any = None,
        _req: Optional[Request] = None,
    ) -> None:
        self.headers = HeadersDict({"X-Request-Id": str(uuid4())})
        self.cookies = CookiesDict()

        self.status_code = status_code
        self.content_type = content_type
        self.charset = charset

        self._app = _app
        self._req = _req
        self._session = {}
        self._etag = None
        self._last_modified = None

    def __call__(self, start_response: Callable) -> Iterable:
        body = self.raw_body or ""
        if hasattr(body, "encode"):
            body = body.encode(self.charset)

        content_length = len(body)
        if content_length:
            self.headers["Content-Length"] = str(content_length)
            self.headers[
                "Content-Type"
            ] = f"{self.content_type}; charset={self.charset}"

        start_response(self.status_code, self.headers_list)
        if not body:
            return []
        return [body]

    def __repr__(self) -> str:
        return f"<Response “{self._status_code}”>"

    @property
    def body(self) -> Optional[str]:
        return self.raw_body

    @body.setter
    def body(self, content: Any) -> None:
        """Sets the response body content. If it is a dictionary,
        encodes it to JSON and sets the content_type to "application/json"
        """
        if isinstance(content, dict):
            self.set_json_body(content)
        else:
            self.set_raw_body(content)

    def set_raw_body(self, content: str) -> None:
        self.raw_body = content

    def set_json_body(self, content: Dict) -> None:
        self.content_type = "application/json"
        self.set_raw_body(json.dumps(content))

    @property
    def has_body(self) -> bool:
        return self.raw_body is not None

    @property
    def headers_list(self) -> List[Tuple]:
        return self._build_regular_headers() + self._build_cookie_headers()

    def _build_regular_headers(self) -> List[Tuple]:
        return [
            (key, tunnel_encode(value, "utf-8")) for key, value in self.headers.items()
        ]

    def _build_cookie_headers(self) -> List[Tuple]:
        if self.disable_cookies:
            return []
        return [
            tuple(morsel.output().split(": ", 1)) for morsel in self.cookies.values()
        ]

    @property
    def session(self) -> Dict[str, Any]:
        """Read-only session"""
        return self._session

    @property
    def status_code(self) -> str:
        return self._status_code

    @status_code.setter
    def status_code(self, value: str) -> None:
        self._status_code = tunnel_encode(value)

    def flash(self, message: str, **data) -> None:
        """Flashes a message for the next request.
        To fetch the flashed message and to display it to the user,
        you must read `req.flashes` in the template.

        Requires an already fetched session.
        """
        flashes = self.session.get(FLASHES_SESSION_KEY, [])
        flashes.append((message, data))
        self.session[FLASHES_SESSION_KEY] = flashes

    def redirect_to(
        self,
        url_or_route: str,
        object: Optional[Any] = None,
        *,
        status_code: str = status.see_other,
        **kwargs,
    ) -> None:
        self.status_code = status_code

        to = url_or_route
        if not url_or_route.startswith(("/", "http")):
            to = self._app.url_for(url_or_route, object=object, **kwargs)

        self.headers["location"] = to
        self.body = "\n".join(
            [
                "<!doctype html>",
                '<meta charset="utf-8">',
                f'<meta http-equiv="refresh" content="0; url={to}">',
                f'<script>window.location.href="{to}"</script>',
                "<title>Page Redirection</title>",
                "If you are not redirected automatically, follow ",
                f'<a href="{to}">this link to the new page</a>.',
            ]
        )

    def set_cookie(self, key: str, value: str = "", **kwargs) -> None:
        """
        Set (add) a cookie for the response. Returns the cookie set.

        Arguments are:

            key:
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
                Should only be "Strict" or "Lax".
                https://www.owasp.org/index.php/SameSite

            comment:
                A string representing the cookie Comment value, or None. If comment
                is None, no Comment value will be sent in the cookie.

        """
        return add_cookie(
            self.cookies, key, value, max_size=self.max_cookie_size, **kwargs
        )

    def unset_cookie(self, name: str) -> None:
        """
        Removes a cookie from this response (before sending it to the client).
        If the cookie is already on the client, use `delete_cookie()` instead.
        """
        if name in self.cookies:
            del self.cookies[name]

    def delete_cookie(
        self,
        name: str,
        *,
        path: str = "/",
        domain: Optional[str] = None
    ) -> None:
        """
        Delete a cookie from the client. Note that path and domain must match
        how the cookie was originally set.

        This sets the cookie to the empty string, and max_age=0 so that it should
        expire immediately.
        """
        self.set_cookie(name, value="", max_age=0, path=path, domain=domain)

    def fresh_when(
        self,
        objects: Any = None,
        *,
        etag: Optional[Union[date, int, float, str]] = None,
        last_modified: Optional[date] = None,
        strong: bool = False,
        public: bool = False,
    ) -> bool:
        """
        Sets the Etag header, the Last-Modified header, or both.

        The Etag can be generated from a date, a string or a number.
        The Last-Modified can be generated from an UTC or naive datetime.
        You can also use an object or a list of objects with an `updated_at` attribute.
        The maximum `updated_at` of that list will be used to set both values.

        Arguments:

        - strong:
            By default a “weak” Etag is used. Set this to `True` to set a “strong” ETag
            validator on the response. A strong ETag implies exact equality: the response
            must match byte for byte. This is necessary for doing range requests within a
            large file or for compatibility with some CDNs that don’t support weak ETags.

        - public:
            By default the Cache-Control header is private, set this to `True` if you want
            your application to be cacheable by other devices (proxy caches).

        """
        if objects:
            if not iterable(objects):
                objects = [objects]
            dates = [obj.updated_at for obj in objects if obj is not None]
            if dates:
                # objects could be a lazy-loaded empty collection
                updated_at = max(dates)
                assert isinstance(
                    updated_at, date
                ), "`updated_at` attribute must be a datetime"
                etag = updated_at
                last_modified = updated_at

        if etag is not None:
            digest = md5(str(etag).encode()).hexdigest()
            self._etag = f'"{digest}"' if strong else f'W/"{digest}"'
            self.headers["ETag"] = self._etag

        if last_modified is not None:
            dt = last_modified
            fmt = f"{DAYS[dt.weekday()]}, %d {MONTHS[dt.month - 1]} %Y %H:%M:%S GMT"
            self._last_modified = dt
            self.headers["Last-Modified"] = dt.strftime(fmt)

        self.headers[
            "Cache-Control"
        ] = f"max-age=0, {'public' if public else 'private'}, must-revalidate"
        return self.is_fresh

    @property
    def is_fresh(self) -> bool:
        if self._req is None:
            return False

        # An ETag has priority over Last-Modified
        if self._req.if_none_match and self._etag:
            if self._etag in self._req.if_none_match:
                return True

        if self._last_modified and self._req.if_modified_since:
            if self._last_modified <= self._req.if_modified_since:
                return True

        return False
