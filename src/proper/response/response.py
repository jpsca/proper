"""
Response class.
"""
import unicodedata
import typing as t
from collections.abc import Iterable
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import quote

from .. import status
from ..helpers import tunnel_encode

from .cookies import ResponseCookiesMixin
from .headers import ResponseHeadersMixin
from .file_wrapper import FileWrapper
from .flash_dict import FlashDict

if t.TYPE_CHECKING:
    from proper import App, Request


__all__ = ("Response",)


def is_iterable(obj: t.Any) -> bool:
    return isinstance(obj, Iterable) and not isinstance(obj, (str, dict))


class Response(ResponseHeadersMixin, ResponseCookiesMixin):
    """
    """

    flash: "FlashDict"

    # Set to `True` by the dispatcher to indicate the endpoint was called.
    dispatched: bool = False

    # Set it to `True` to stop the normal flow and return inmediatly.
    # Safety not guaranteed. I'm kidding, it was never guaranteed to begin with.
    stop: bool = False

    # name of the component
    component: str | None = None

    error: Exception | None = None
    body: str | bytes | t.Iterable[bytes] | None = None

    _app: "App | None" = None
    _request: "Request | None" = None
    _session: dict[str, t.Any]

    def __init__(
        self,
        status_code: str = status.ok,
        *,
        charset: str = "utf-8",
        _app: "App | None" = None,
        _request: "Request | None" = None,
        **environ: t.Any,
    ) -> None:
        self.status_code = status_code
        self.charset = charset
        self._app = _app
        self._request = _request
        self._session = {}
        self.environ = environ

        self.flash = FlashDict(self)
        super().__init__()

    def __call__(self, start_response: t.Callable) -> t.Iterable[bytes]:
        body = self.body

        if not body:
            body = b""

        if isinstance(body, str):
            body = body.encode(self.charset)

        if isinstance(body, bytes):
            if self.content_length is None:
                self.set_content_length(len(body))
            body = [body]

        if self.content_type is None:
            self.set_content_type(self.content_type, charset=self.charset)

        headers = [*self._get_header_tuples(), self._get_cookie_tuple()]
        start_response(self.status_code, headers)
        return body

    def __repr__(self) -> str:
        return f"<Response “{self._status_code}”>"

    @property
    def has_body(self) -> bool:
        """Returns `True` if the response has a body."""
        return self.body is not None

    @property
    def session(self) -> dict:
        """Read-only session"""
        return self._session

    @property
    def status_code(self) -> str:
        """The status code of the response."""
        return self._status_code

    @status_code.setter
    def status_code(self, value: str) -> None:
        self._status_code = tunnel_encode(value)

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
        """
        Redirects to the given URL or route.

        Args:
            url_or_route: The URL or route to redirect to.
            object: The object to pass to the route.
            flash: The flash message to set.
            flash_type: Optional type of the flash message.
            status_code: The status code to use.
            **kw: Additional keyword arguments to pass to the route.

        """
        assert self._app
        self.status_code = status_code
        to = url_or_route
        if not url_or_route.startswith(("/", "http")):
            to = self._app.url_for(url_or_route, object=object, **kw)

        self.set_location(to)
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

    def fresh_when(
        self,
        objects: t.Any = None,
        *,
        etag: datetime | int | float | str | None = None,
        last_modified: datetime | None = None,
        strong: bool = False,
        public: bool = False,
    ) -> bool:
        """Sets the Etag header, the Last-Modified header, or both.

        The Etag can be generated from a date, a string or a number.
        The Last-Modified can be generated from an UTC or naive datetime.
        You can also use an object or a list of objects with an `updated_at` attribute.
        The maximum `updated_at` of that list will be used to set both values.

        Args:
            strong:
                By default a “weak” Etag is used. Set this to `True` to set a “strong” ETag
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
        return self.is_fresh

    @property
    def is_fresh(self) -> bool:
        """Returns `True` if the response is fresh."""
        if self._request is None:
            return False

        # An ETag has priority over Last-Modified
        if self.etag and self._request.if_none_match:
            if self.etag in self._request.if_none_match:
                return True

        if self.last_modified and self._request.if_modified_since:
            if self.last_modified <= self._request.if_modified_since:
                return True

        return False

    def send_file(
        self,
        path: str | Path,
        *,
        mimetype: str | None = None,
        as_attachment: bool = False,
        download_name: str | None = None,
        use_x_sendfile: bool | None = None,
    ) -> None:
        """Sends a file as response.

        Args:
            path: The path to the file.
            mimetype: The mimetype of the file.
            as_attachment: If `True` the file will be sent as attachment.
            download_name: The name of the file.
            use_x_sendfile: If `True` the X-Sendfile header will be used.

        """
        path = Path(path).resolve()
        download_name = download_name or path.name

        if mimetype is None:
            mimetype, encoding = guess_type(path)
            mimetype = mimetype or "application/octet-stream"

            # Don't send encoding for attachments, it causes browsers to
            # save decompress tar.gz files.
            if not as_attachment:
                self.set_content_encoding(encoding)

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

        self.set_header("Content-Disposition", f"{value}{options}")

        if use_x_sendfile:
            self.set_header("X-Sendfile", path)

        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime

        if size is not None:
            self.set_content_length(size)
        if mtime is not None:
            self.set_last_modified(mtime)

        self.body = self.wrap_file(path.open("rb"))

    def wrap_file(self, file: t.IO[t.Any], buffer_size: int = 8192) -> t.Iterable[bytes]:
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
