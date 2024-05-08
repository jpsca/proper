"""
Response class.
"""
import typing as t
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import quote
from wsgiref.types import StartResponse

from proper import current
from proper import status as pstatus
from proper.helpers import DotDict, tunnel_encode
from proper.types import TBody, TReadable

from .cookies import ResponseCookiesMixin
from .file_wrapper import FileWrapper
from .flash_dict import FlashDict
from .headers import ResponseHeadersMixin


if t.TYPE_CHECKING:
    from proper.helpers import Proxy
    from proper.request import Request


__all__ = ("Response",)


def is_iterable(obj: t.Any) -> bool:
    return isinstance(obj, Iterable) and not isinstance(obj, (str, dict))


class Response(ResponseHeadersMixin, ResponseCookiesMixin):
    """ """

    flash: "FlashDict"
    error: Exception | None = None
    body: TBody | str | None = None
    session: DotDict

    def __init__(
        self,
        status: str = pstatus.ok,
        **environ: t.Any,
    ) -> None:
        self.status = status
        self.environ = environ
        self.session = DotDict()
        self.flash = FlashDict(self)
        super().__init__()

    def __call__(self, start_response: StartResponse) -> TBody:
        body = self.prepare_body()
        headers = self.get_headers_list()
        start_response(tunnel_encode(self.status), headers)
        return body

    def __repr__(self) -> str:
        return f"<Response “{self.status}”>"

    @property
    def has_body(self) -> bool:
        """Returns `True` if the response has a body."""
        return self.body is not None

    @property
    def status_code(self) -> int:
        """The status code of the response."""
        return int(self.status.split(" ", 1)[0])

    def prepare_body(self) -> TBody:
        body = self.body

        if not body:
            body = b""

        if isinstance(body, str):
            body = body.encode(self.charset)

        if isinstance(body, bytes):
            if not self.content_length:
                self.set_content_length(len(body))
            body = [body]

        return body

    def get_headers_list(self) -> list[tuple[str, str]]:
        return [*self._get_header_tuples(), *self._get_cookie_tuples()]

    def redirect_to(
        self,
        url_or_route: str,
        obj: t.Any = None,
        *,
        flash: str | None = None,
        flash_type: str = "notice",
        status: str = pstatus.see_other,
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

            flash_type:
                Optional type of the flash message.

            status (str):
                The status code to use, e.g.: "303 See Other"

            **kw:
                Additional keyword arguments to pass to the route.

        """
        assert current.app
        self.status = status
        to = url_or_route
        if not url_or_route.startswith(("/", "http")):
            to = current.app.url_for(url_or_route, object=obj, **kw)

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
        last_modified: datetime | float | int | None = None,
        strong: bool = False,
        public: bool = False,
        request: "Request | Proxy | None" = None,
    ) -> bool:
        """Sets the Etag header, the Last-Modified header, or both.

        The Etag can be generated from a date, a string or a number.
        The Last-Modified can be generated from an UTC or naive datetime.
        You can also use an object or a list of objects with an `updated_at` attribute.
        The maximum `updated_at` of that list will be used to set both values.

        Arguments:

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
        return self.is_fresh(request)

    def is_fresh(self, request: "Request | Proxy | None" = None) -> bool:
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
            relpath = path.relative_to(current.app.root_path.parent)
            self.headers[x_sendfile_header] = f"/{relpath}"
            self.set_content_length(0)
            self.body = ""
            return

        if stat.st_size is not None:
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
        self.body = self._wrap_file(path.open("rb"))

    def _wrap_file(
        self,
        file: TReadable,
        block_size: int = 8192,
    ) -> t.Iterable[bytes]:
        """Wraps a file using the WSGI server's file wrapper

        More information about file wrappers is available in
        [PEP 3333](https://peps.python.org/pep-3333/#optional-platform-specific-file-handling).

        Arguments:

            file:
                A file-like object with a `read` method.

            block_size:
                Number of bytes for one iteration.

        """
        assert self.environ is not None
        file_wrapper = self.environ.get("wsgi.file_wrapper") or FileWrapper
        return file_wrapper(file, block_size)
