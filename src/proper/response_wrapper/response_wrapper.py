"""
Response class.
"""
from collections.abc import Iterable
from datetime import date
from hashlib import md5
from typing import TYPE_CHECKING

from .. import status
from ..helpers import HeadersDict, tunnel_encode

from .cookies import CookiesDict, add_cookie
from .flash_dict import FlashDict

if TYPE_CHECKING:
    from http.cookies import Morsel
    from typing import (
        Any,
        Callable,
        Dict,
        List,
        Optional,
        Tuple,
        Union,
    )
    from proper import App, Request


__all__ = ("Response",)


def is_iterable(obj: "Any") -> bool:
    return isinstance(obj, Iterable) and not isinstance(obj, (str, dict))


class Response:
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    MONTHS = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    DEFAULT_MAX_COOKIE_SIZE = 4093
    TYPES_MAP = {
        "css": "text/css",
        "csv": "text/csv",
        "gif": "image/gif",
        "heic": "image/heic",
        "heif": "image/heif",
        "html": "text/html",
        "ico": "image/vnd.microsoft.icon",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "js": "application/javascript",
        "json": "application/json",
        "mp3": "audio/mpeg",
        "mp4": "video/mp4",
        "pdf": "application/pdf",
        "png": "image/png",
        "svg": "image/svg+xml",
        "txt": "text/plain",
        "webm": "video/webm",
        "webmanifest": "application/manifest+json",
        "xls": "application/vnd.ms-excel",
    }

    headers: "HeadersDict"
    cookies: "CookiesDict"
    flash: "FlashDict"

    # Set to `True` by the dispatcher to indicate the endpoint was called.
    dispatched: bool = False

    # Set it to `True` to stop the normal flow and return inmediatly.
    # Safety not guaranteed. I'm kidding, it was never guaranteed to begin with.
    stop: bool = False

    # name of the component
    component: "Optional[str]" = None

    # Warn if a cookie header exceeds this size.
    # The default is 4093 and should be supported by most browsers
    # (See http://browsercookielimits.squawky.net)
    # A cookie larger than this size will still be sent, but it may be ignored or
    # handled incorrectly by some browsers. Set to 0 to disable this check.
    max_cookie_size: int = DEFAULT_MAX_COOKIE_SIZE

    # Set to True to not set cookies in this response, including any changes to the
    # session or CSRF token. You might want to use it for some read-only public
    # endpoints, like a RSS feed.
    disable_cookies: bool = False

    error: "Optional[Exception]" = None
    raw_body: "Union[str, bytes, None]" = None

    _etag: "Optional[str]" = None
    _last_modified: "Optional[date]" = None
    _app: "Optional[App]" = None
    _request: "Optional[Request]" = None
    _session: "Dict[str, Any]"

    def __init__(
        self,
        status_code: str = status.ok,
        content_type: str = "text/html",
        charset: str = "utf-8",
        _app: "Optional[App]" = None,
        _request: "Optional[Request]" = None,
    ) -> None:
        self.status_code = status_code
        self.content_type = content_type
        self.charset = charset
        self._app = _app
        self._request = _request
        self._session = {}

        self.headers = HeadersDict()
        self.cookies = CookiesDict()
        self.flash = FlashDict(self)

    def __call__(self, start_response: "Callable") -> "Iterable[bytes]":
        body: "Union[str, bytes]" = self.raw_body or b""  # type: ignore
        if isinstance(body, str):
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

    # @classmethod
    # def send_file(
    #     self,
    #     filename: str,
    #     status_code: str = status.http_302,
    #     content_type: str = ""):
    #     """Send file contents in a response.

    #     Args:
    #         filename (str): The filename of the file.
    #         status_code (str): The 3xx status code to use for the redirect. The
    #             default is 302.
    #         content_type (str): The `Content-Type` header to use in the
    #             response. If omitted, it is generated automatically
    #             from the file extension.

    #     IMPORTANT: The filename is assumed to be trusted. Never pass filenames
    #     provided by the user without validating and sanitizing them first.
    #     """
    #     if not content_type:
    #         ext = filename.split(".")[-1].lower()
    #         if ext in cls.TYPES_MAP:
    #             content_type = cls.TYPES_MAP[ext]
    #         else:
    #             content_type = "application/octet-stream"

    #     self.status_code = status_code
    #     self.content_type = content_type
    #     self.headers["Content-Type"] = content_type
    #     self.start_response(status_code, self.headers_list)
    #     return open(filename, "rb")

    @property
    def body(self) -> "Union[str, bytes, None]":
        return self.raw_body

    @body.setter
    def body(self, content: "Any") -> None:
        """Sets the response body content."""
        if isinstance(content, (str, bytes)):
            self.raw_body = content
        else:
            self.raw_body = str(content)

    @property
    def has_body(self) -> bool:
        return self.raw_body is not None

    @property
    def headers_list(self) -> "List[Tuple]":
        return self._build_regular_headers() + self._build_cookie_headers()

    def _build_regular_headers(self) -> "List[Tuple]":
        return [
            (key, tunnel_encode(value, "utf-8")) for key, value in self.headers.items()
        ]

    def _build_cookie_headers(self) -> "List[Tuple]":
        if self.disable_cookies:
            return []
        return [
            tuple(morsel.output().split(": ", 1)) for morsel in self.cookies.values()
        ]

    @property
    def session(self) -> dict:
        """Read-only session"""
        return self._session

    @property
    def status_code(self) -> str:
        return self._status_code

    @status_code.setter
    def status_code(self, value: str) -> None:
        self._status_code = tunnel_encode(value)

    def set_header(self, name: str, value: str) -> None:
        self.headers[name] = value

    def redirect_to(
        self,
        url_or_route: str,
        object: "Any" = None,
        *,
        flash: "Optional[str]" = None,
        flash_type: str = "notice",
        status_code: str = status.see_other,
        **kw,
    ) -> None:
        assert self._app
        self.status_code = status_code
        to = url_or_route
        if not url_or_route.startswith(("/", "http")):
            to = self._app.url_for(url_or_route, object=object, **kw)

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

        if flash:
            self.flash[flash_type] = flash

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
        If the cookie is already on the client, use `delete_cookie()` instead.
        """
        if name in self.cookies:
            del self.cookies[name]

    def delete_cookie(self, name: str, *, path: str = "/", domain: str = "") -> None:
        """
        Delete a cookie from the client. Note that path and domain must match
        how the cookie was originally set.

        This sets the cookie to the empty string, and max_age=0 so that it should
        expire immediately.
        """
        self.set_cookie(name, value="", max_age=0, path=path, domain=domain)

    def fresh_when(
        self,
        objects: "Any" = None,
        *,
        etag: "Union[date, int, float, str, None]" = None,
        last_modified: "Optional[date]" = None,
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
            if not is_iterable(objects):
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
            fmt = f"{self.DAYS[dt.weekday()]}, %d {self.MONTHS[dt.month - 1]} %Y %H:%M:%S GMT"
            self._last_modified = dt
            self.headers["Last-Modified"] = dt.strftime(fmt)

        self.headers[
            "Cache-Control"
        ] = f"max-age=0, {'public' if public else 'private'}, must-revalidate"
        return self.is_fresh

    @property
    def is_fresh(self) -> bool:
        if self._request is None:
            return False

        # An ETag has priority over Last-Modified
        if self._request.if_none_match and self._etag:
            if self._etag in self._request.if_none_match:
                return True

        if self._last_modified and self._request.if_modified_since:
            if self._last_modified <= self._request.if_modified_since:
                return True

        return False
