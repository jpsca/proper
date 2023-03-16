"""
Response class.
"""
import unicodedata
import typing as t
from collections.abc import Iterable
from datetime import date, datetime
from hashlib import sha1
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import quote

from .. import status
from ..helpers import tunnel_encode

from .cookies import CookiesDict, add_cookie
from .headers import ResponseHeaders
from .file_wrapper import FileWrapper
from .flash_dict import FlashDict

if t.TYPE_CHECKING:
    from http.cookies import Morsel
    from proper import App, Request


__all__ = ("Response",)


def is_iterable(obj: t.Any) -> bool:
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

    headers: ResponseHeaders
    cookies: "CookiesDict"
    flash: "FlashDict"

    # Set to `True` by the dispatcher to indicate the endpoint was called.
    dispatched: bool = False

    # Set it to `True` to stop the normal flow and return inmediatly.
    # Safety not guaranteed. I'm kidding, it was never guaranteed to begin with.
    stop: bool = False

    # name of the component
    component: str | None = None

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

    error: Exception | None = None
    raw_body: str | bytes | None = None

    _etag: str | None = None
    _last_modified: date | None = None
    _app: "App | None" = None
    _request: "Request | None" = None
    _session: dict[str, t.Any]

    def __init__(
        self,
        status_code: str = status.ok,
        content_type: str = "text/html",
        charset: str = "utf-8",
        *,
        _app: "App | None" = None,
        _request: "Request | None" = None,
        **environ: t.Any,
    ) -> None:
        self.status_code = status_code
        self.content_type = content_type
        self.charset = charset
        self._app = _app
        self._request = _request
        self._session = {}
        self.environ = environ

        self.headers = ResponseHeaders()
        self.cookies = CookiesDict()
        self.flash = FlashDict(self)

    def __call__(self, start_response: t.Callable) -> t.Iterable[bytes]:
        if "Content-Type" not in self.headers:
            content_type = f"{self.content_type}; charset={self.charset}"
            self.headers["Content-Type"] = content_type

        body = self.raw_body or b""
        if isinstance(body, str):
            body = body.encode(self.charset)

        if "Content-Length" not in self.headers:
            content_length = len(body)
            if content_length:
                self.headers["Content-Length"] = str(content_length)

        start_response(self.status_code, self.headers_list)
        if not body:
            return []
        return [body]

    def __repr__(self) -> str:
        return f"<Response “{self._status_code}”>"

    @property
    def body(self) -> str | bytes | None:
        return self.raw_body

    @body.setter
    def body(self, content: t.Any) -> None:
        """Sets the response body content."""
        if isinstance(content, (str, bytes)):
            self.raw_body = content
        else:
            self.raw_body = str(content)

    @property
    def has_body(self) -> bool:
        return self.raw_body is not None

    @property
    def headers_list(self) -> list[tuple[str, str]]:
        return self._build_regular_headers() + self._build_cookie_headers()

    def _build_regular_headers(self) -> list[tuple[str, str]]:
        return [
            (key, tunnel_encode(value, "utf-8"))
            for key, value in self.headers.items()
        ]

    def _build_cookie_headers(self) -> list[tuple[str, str]]:
        if self.disable_cookies:
            return []
        return [
            tuple(morsel.output().split(": ", 1))
            for morsel in self.cookies.values()
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
        object: t.Any = None,
        *,
        flash: str | None = None,
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
        objects: t.Any = None,
        *,
        etag: date | int | float | str | None = None,
        last_modified: date | None = None,
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
            self.set_etag(etag, strong=strong)

        if last_modified is not None:
            self.set_last_modified(last_modified)

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

    def set_etag(self, etag: date | int | float | str, *, strong: bool = False) -> None:
        """
        Sets the Etag header.

        The Etag can be generated from a date, a string or a number.

        Arguments:
            - strong:
                By default a “weak” Etag is used. Set this to `True` to set a
                “strong” ETag validator on the response. A strong ETag implies
                exact equality: the response must match byte for byte.
                This is necessary for doing range requests within a large file
                or for compatibility with some CDNs that don’t support weak ETags.

        """
        assert etag is not None
        digest = sha1(str(etag).encode()).hexdigest()
        self._etag = f'"{digest}"' if strong else f'W/"{digest}"'
        self.headers["ETag"] = self._etag

    def set_last_modified(self, dt: date | float | int) -> None:
        """
        Sets the Last-Modified header.

        The Last-Modified can be generated from a timestamp of rom an UTC or naive datetime.
        """
        assert dt is not None
        if isinstance(dt, (float, int)):
            dt = datetime.utcfromtimestamp(dt)
        fmt = f"{self.DAYS[dt.weekday()]}, %d {self.MONTHS[dt.month - 1]} %Y %H:%M:%S GMT"
        self._last_modified = dt
        self.headers["Last-Modified"] = dt.strftime(fmt)

    def send_file(
        self,
        path: str | Path,
        *,
        mimetype: str | None = None,
        as_attachment: bool = False,
        download_name: str | None = None,
        use_x_sendfile: bool | None = None,
    ) -> None:
        path = Path(path).resolve()
        download_name = download_name or path.name

        if mimetype is None:
            mimetype, encoding = guess_type(path)
            mimetype = mimetype or "application/octet-stream"

            # Don't send encoding for attachments, it causes browsers to
            # save decompress tar.gz files.
            if encoding is not None and not as_attachment:
                self.headers["Content-Encoding"] = encoding

        try:
            download_name.encode("ascii")
        except UnicodeEncodeError:
            simple = unicodedata.normalize("NFKD", download_name)
            simple = simple.encode("ascii", "ignore").decode("ascii")
            # safe = RFC 5987 attr-char
            quoted = quote(download_name, safe="!#$&+-.^_`|~")
            options = f"; filename={simple}; filename*=UTF-8''{quoted}"
        else:
            options = f"; filename={download_name}"

        value = "attachment" if as_attachment else "inline"
        self.headers["Content-Disposition"] = f"{value}{options}"

        if use_x_sendfile:
            self.headers["X-Sendfile"] = path

        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime

        if size is not None:
            self.headers["Content-Length"] = str(size)
        if mtime is not None:
            self.set_last_modified(mtime)

        self.body = self.wrap_file(path.open("rb"))

    def wrap_file(self, file: t.IO[bytes], buffer_size: int = 8192) -> t.Iterable[bytes]:
        """Wraps a file using the WSGI server's file wrapper

        More information about file wrappers is available in
        [PEP 3333](https://peps.python.org/pep-3333/#optional-platform-specific-file-handling).

        Attrs:
            file: a file-like object with a `read` method.
            buffer_size: number of bytes for one iteration.

        """
        assert self.environ is not None
        file_wrapper = self.environ.get("wsgi.file_wrapper") or FileWrapper
        return file_wrapper(file, buffer_size)
