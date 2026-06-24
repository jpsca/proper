"""
Response class.
"""
import html as html_mod
import typing as t
import unicodedata
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import quote

from ... import status as pstatus
from ...constants import HEAD, SIGNED_COOKIE_SALT
from ...global_context import current
from ...helpers import DotDict
from ...types import Iterable, TBody, TScope
from .cookies import make_cookie, validate_cookie_size
from .file_wrapper import FileWrapper
from .flash_messages import FlashMessages
from .headers import ResponseHeadersMixin


if t.TYPE_CHECKING:
    from http.cookies import Morsel

    from ...app import App
    from ..request import Request


__all__ = ("Response",)


def is_iterable(obj: t.Any) -> bool:
    return isinstance(obj, Iterable) and not isinstance(obj, (str, dict))


class Response(ResponseHeadersMixin):
    """ """

    flash: FlashMessages
    body: TBody | str | None = None
    status: int = pstatus.ok
    cookies: "dict[str, Morsel]"

    # Warn if a cookie header exceeds this size.
    # The default is 4093 and should be supported by most browsers
    # (See http://browsercookielimits.squawky.net)
    # A cookie larger than this size will still be sent, but it may be ignored or
    # handled incorrectly by some browsers. Set to 0 to disable this check.
    max_cookie_size: int = 4093

    # Set to True to not set cookies in this response, including any changes to the
    # session. You might want to use it for some read-only public endpoints, like a RSS feed.
    disable_cookies: bool = False

    _error: Exception | None = None
    _session: DotDict

    def __init__(
        self,
        scope: TScope,
        *,
        status: int = pstatus.ok,
    ) -> None:
        self.scope = scope
        self.status = status
        self._session = DotDict()
        self.flash = FlashMessages(self)
        self.cookies = {}
        super().__init__()

    def __repr__(self) -> str:
        return f"<Response {self.status}>"

    @property
    def app(self) -> "App":
        return self.scope["app"]

    @property
    def session(self) -> DotDict:
        return self._session

    @session.setter
    def session(self, value: dict | DotDict) -> None:
        self._session = DotDict(value)

    @property
    def has_body(self) -> bool:
        """Returns `True` if the response has a body."""
        return self.body is not None

    @property
    def status_code(self) -> int:
        """The status code of the response."""
        return self.status

    @property
    def error(self) -> Exception | None:
        """The error that caused this response, if any."""
        return self._error

    @error.setter
    def error(self, value: Exception | None) -> None:
        self._error = value
        self.status = getattr(value, "status", pstatus.server_error)
        headers = getattr(value, "headers", {})
        if headers:
            for name, value in headers.items():
                self.headers[name] = value

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
        samesite: t.Literal["Lax", "Strict", "None"] | None = "Lax",
        comment: str = "",
        signed: bool = False,
        salt: str = SIGNED_COOKIE_SALT,
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
                If samesite is Python `None`, no SameSite value will be sent.
                Should be `"Lax"`, `"Strict"`, `"None"`, or Python `None`.
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
        if signed:
            value = self.app.dumps(value, salt=salt)
        elif not isinstance(value, (str, bytes)):
            value = str(value)

        cookie = make_cookie(
            name=name,
            value=value,
            max_age=max_age,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
            comment=comment,
        )
        name = cookie.key
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
        samesite: t.Literal["Lax", "Strict", "None"] | None = "Lax",
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

    def redirect_to(
        self,
        url_or_route: str,
        obj: t.Any = None,
        *,
        flash: str | None = None,
        flash_cat: str = "positive",
        status: int = pstatus.see_other,
        **kw,
    ) -> None:
        """
        Redirects to the given URL or route.

        Arguments:
            url_or_route:
                The URL or route to redirect to.
            obj:
                The object to build the route
            flash:
                Optional flash message to set.
            flash_cat:
                Optional category of the flash message.
            status (int):
                The status code to use, e.g.: 303 (See Other)
            **kw:
                Additional keyword arguments to pass to the route.

        """
        self.status = status
        to = url_or_route
        if not url_or_route.startswith(("/", "http")):
            assert self.app
            to = self.app.url_for(url_or_route, object=obj, **kw)

        self.set_location(to)
        escaped = html_mod.escape(to, quote=True)
        self.body = "\n".join(
            [
                "<!doctype html>",
                '<meta charset="utf-8">',
                f'<meta http-equiv="refresh" content="0; url={escaped}">',
                f'<script>window.location.href="{escaped}"</script>',
                "<title>Page Redirection</title>",
                "If you are not redirected automatically, follow ",
                f'<a href="{escaped}">this link to the new page</a>.',
            ]
        )

        if flash:
            self.flash.message(flash_cat, flash)

    def fresh_when(
        self,
        objects: t.Any = None,
        *,
        etag: datetime | int | float | str | None = None,
        last_modified: datetime | float | int | None = None,
        strong: bool = False,
        public: bool = False,
        request: "Request | None" = None,
    ) -> bool:
        """Sets the Etag header, the Last-Modified header, or both.

        The Etag can be generated from a date, a string or a number.
        The Last-Modified can be generated from an UTC or naive datetime.
        You can also use an object or a list of objects with an `updated_at` attribute.
        The maximum `updated_at` of that list will be used to set both values.

        Arguments:
            strong:
                By default a "weak" Etag is used. Set this to `True` to set a "strong" ETag
                validator on the response. A strong ETag implies exact equality: the response
                must match byte for byte. This is necessary for doing range requests within a
                large file or for compatibility with some CDNs that don’t support weak ETags.
            public:
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
                    updated_at, datetime
                ), "`updated_at` attribute must be a datetime"
                etag = updated_at
                last_modified = updated_at

        self.set_etag(etag, strong=strong)
        self.set_last_modified(last_modified)
        self.set_cache_control(
            "max-age=0",
            "public" if public else "private",
            "must-revalidate",
        )
        return self.is_fresh(request)

    def is_fresh(self, request: "Request | None" = None) -> bool:
        """Returns `True` if the response is fresh."""
        request = current.request if request is None else request
        if request is None:
            return False

        # An ETag has priority over Last-Modified
        if self.etag and request.if_none_match:
            if self.etag in request.if_none_match:
                return True

        if self.last_modified and request.if_modified_since:
            if self.last_modified <= request.if_modified_since:
                return True

        return False

    def send_file(
        self,
        path: str | Path,
        *,
        mimetype: str | None = None,
        as_attachment: bool = False,
        download_name: str | None = None,
        x_sendfile_header: str = "",
    ) -> None:
        """Sends a file as a response, unless the cache headers
        indicate it's not necessary.

        Arguments:
            path:
                The path to the file.
            mimetype:
                The mimetype of the file.
            as_attachment [False]:
                If `True` the file will be sent as attachment.
            download_name:
                The name of the file.
            x_sendfile_header:
                If not empty, set the filepath in this header and let
                the proxy/webserver take care of returning the file.

        """
        path = Path(path).resolve()
        stat = path.stat()

        self.set_last_modified(stat.st_mtime)

        if x_sendfile_header:
            assert self.app
            relpath = path.relative_to(self.app.root_path.parent)
            self.headers[x_sendfile_header] = f"/{relpath}"
            self.set_content_length(0)
            self.body = ""
            return

        self.set_content_length(stat.st_size)

        if mimetype is None:
            mimetype, encoding = guess_type(path)
            mimetype = mimetype or "application/octet-stream"

            # Don't send encoding for attachments, it causes browsers to
            # save decompressed tar.gz files.
            if encoding and not as_attachment:
                self.set_content_encoding(encoding)
            else:
                self.set_content_encoding()

        self.content_type = mimetype

        download_name = download_name or path.name
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

        self.headers["content-disposition"] = f"{value}{options}"
        self.body = FileWrapper(path.open("rb"), block_size=8192)

    def get_cookie_tuples(self) -> list[tuple[str, str]]:
        if self.disable_cookies or not self.cookies:
            return []

        return [
            ("Set-Cookie", morsel.OutputString())
            for morsel in self.cookies.values()
        ]

    def get_headers_list(self) -> list[tuple[str, str]]:
        return [*self.get_header_tuples(), *self.get_cookie_tuples()]

    def prepare(
        self,
    ) -> "tuple[int, list[tuple[bytes, bytes]], bytes | Iterable[bytes]]":
        """Prepare the response for sending through ASGI."""
        body = self.body or b""
        body_out: bytes | Iterable[bytes]

        if isinstance(body, str):
            body_out = body.encode(self.charset)
        elif isinstance(body, (bytes, bytearray, memoryview)):
            body_out = bytes(body)
        else:
            # Iterable (e.g. FileWrapper) - pass through for streaming.
            # Content-Length should already be set by the caller (e.g. send_file).
            body_out = body

        if isinstance(body_out, bytes) and not self.content_length:
            self.set_content_length(len(body_out))

        enc_headers: list[tuple[bytes, bytes]] = [
            (name.encode("latin-1"), value.encode("latin-1"))
            for name, value in self.get_headers_list()
        ]

        if current.request and current.request.request_method == HEAD:
            body_out = b""
        return self.status, enc_headers, body_out
