"""
Response class.
"""
import unicodedata
import typing as t
from collections.abc import Iterable
from datetime import date
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
    raw_body: str | bytes | None = None

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

        self.flash = FlashDict(self)

    def __call__(self, start_response: t.Callable) -> t.Iterable[bytes]:
        if "Content-Type" not in self._headers:
            content_type = f"{self.content_type}; charset={self.charset}"
            self._headers["Content-Type"] = content_type

        body = self.raw_body or b""
        if isinstance(body, str):
            body = body.encode(self.charset)

        if "Content-Length" not in self._headers:
            content_length = len(body)
            if content_length:
                self._headers["Content-Length"] = str(content_length)

        start_response(self.status_code, self._get_headers_tuples())
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
    def session(self) -> dict:
        """Read-only session"""
        return self._session

    @property
    def status_code(self) -> str:
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
        assert self._app
        self.status_code = status_code
        to = url_or_route
        if not url_or_route.startswith(("/", "http")):
            to = self._app.url_for(url_or_route, object=object, **kw)

        self._headers["location"] = to
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

        self._headers[
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
                self._headers["Content-Encoding"] = encoding

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
        self._headers["Content-Disposition"] = f"{value}{options}"

        if use_x_sendfile:
            self._headers["X-Sendfile"] = path

        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime

        if size is not None:
            self._headers["Content-Length"] = str(size)
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

    def  _get_headers_tuples(self) -> list[tuple[bytes, str]]:
        exclude = []
        if self.disable_cookies:
            exclude.append("cookie")
        return self._headers.get_tuples(exclude)




    cache_control = header_property(
        'Cache-Control',
        """Set the Cache-Control header.
        Used to set a list of cache directives to use as the value of the
        Cache-Control header. The list will be joined with ", " to produce
        the value for the header.
        """,
        format_header_value_list,
    )

    content_location = header_property(
        'Content-Location',
        """Set the Content-Location header.
        This value will be URI encoded per RFC 3986. If the value that is
        being set is already URI encoded it should be decoded first or the
        header should be set manually using the set_header method.
        """,
        uri_encode,
    )

    content_length = header_property(
        'Content-Length',
        """Set the Content-Length header.
        This property can be used for responding to HEAD requests when you
        aren't actually providing the response body, or when streaming the
        response. If either the `text` property or the `data` property is set
        on the response, the framework will force Content-Length to be the
        length of the given text bytes. Therefore, it is only necessary to
        manually set the content length when those properties are not used.
        Note:
            In cases where the response content is a stream (readable
            file-like object), Falcon will not supply a Content-Length header
            to the server unless `content_length` is explicitly set.
            Consequently, the server may choose to use chunked encoding in this
            case.
        """,
    )

    content_range = header_property(
        'Content-Range',
        """A tuple to use in constructing a value for the Content-Range header.
        The tuple has the form (*start*, *end*, *length*, [*unit*]), where *start* and
        *end* designate the range (inclusive), and *length* is the
        total length, or '\\*' if unknown. You may pass ``int``'s for
        these numbers (no need to convert to ``str`` beforehand). The optional value
        *unit* describes the range unit and defaults to 'bytes'
        Note:
            You only need to use the alternate form, 'bytes \\*/1234', for
            responses that use the status '416 Range Not Satisfiable'. In this
            case, raising ``falcon.HTTPRangeNotSatisfiable`` will do the right
            thing.
        (See also: RFC 7233, Section 4.2)
        """,
        format_range,
    )

    content_type = header_property(
        'Content-Type',
        """Sets the Content-Type header.
        The ``falcon`` module provides a number of constants for
        common media types, including ``falcon.MEDIA_JSON``,
        ``falcon.MEDIA_MSGPACK``, ``falcon.MEDIA_YAML``,
        ``falcon.MEDIA_XML``, ``falcon.MEDIA_HTML``,
        ``falcon.MEDIA_JS``, ``falcon.MEDIA_TEXT``,
        ``falcon.MEDIA_JPEG``, ``falcon.MEDIA_PNG``,
        and ``falcon.MEDIA_GIF``.
        """,
    )

    downloadable_as = header_property(
        'Content-Disposition',
        """Set the Content-Disposition header using the given filename.
        The value will be used for the ``filename`` directive. For example,
        given ``'report.pdf'``, the Content-Disposition header would be set
        to: ``'attachment; filename="report.pdf"'``.
        As per `RFC 6266 <https://tools.ietf.org/html/rfc6266#appendix-D>`_
        recommendations, non-ASCII filenames will be encoded using the
        ``filename*`` directive, whereas ``filename`` will contain the US
        ASCII fallback.
        """,
        functools.partial(format_content_disposition, disposition_type='attachment'),
    )

    viewable_as = header_property(
        'Content-Disposition',
        """Set an inline Content-Disposition header using the given filename.
        The value will be used for the ``filename`` directive. For example,
        given ``'report.pdf'``, the Content-Disposition header would be set
        to: ``'inline; filename="report.pdf"'``.
        As per `RFC 6266 <https://tools.ietf.org/html/rfc6266#appendix-D>`_
        recommendations, non-ASCII filenames will be encoded using the
        ``filename*`` directive, whereas ``filename`` will contain the US
        ASCII fallback.
        .. versionadded:: 3.1
        """,
        functools.partial(format_content_disposition, disposition_type='inline'),
    )

    etag = header_property(
        'ETag',
        """Set the ETag header.
        The ETag header will be wrapped with double quotes ``"value"`` in case
        the user didn't pass it.
        """,
        format_etag_header,
    )

    expires = header_property(
        'Expires',
        """Set the Expires header. Set to a ``datetime`` (UTC) instance.
        Note:
            Falcon will format the ``datetime`` as an HTTP date string.
        """,
        dt_to_http,
    )

    last_modified = header_property(
        'Last-Modified',
        """Set the Last-Modified header. Set to a ``datetime`` (UTC) instance.
        Note:
            Falcon will format the ``datetime`` as an HTTP date string.
        """,
        dt_to_http,
    )

    location = header_property(
        'Location',
        """Set the Location header.
        This value will be URI encoded per RFC 3986. If the value that is
        being set is already URI encoded it should be decoded first or the
        header should be set manually using the set_header method.
        """,
        uri_encode,
    )

    retry_after = header_property(
        'Retry-After',
        """Set the Retry-After header.
        The expected value is an integral number of seconds to use as the
        value for the header. The HTTP-date syntax is not supported.
        """,
        str,
    )

    vary = header_property(
        'Vary',
        """Value to use for the Vary header.
        Set this property to an iterable of header names. For a single
        asterisk or field value, simply pass a single-element ``list``
        or ``tuple``.
        The "Vary" header field in a response describes what parts of
        a request message, aside from the method, Host header field,
        and request target, might influence the origin server's
        process for selecting and representing this response.  The
        value consists of either a single asterisk ("*") or a list of
        header field names (case-insensitive).
        (See also: RFC 7231, Section 7.1.4)
        """,
        format_header_value_list,
    )

    accept_ranges = header_property(
        'Accept-Ranges',
        """Set the Accept-Ranges header.
        The Accept-Ranges header field indicates to the client which
        range units are supported (e.g. "bytes") for the target
        resource.
        If range requests are not supported for the target resource,
        the header may be set to "none" to advise the client not to
        attempt any such requests.
        Note:
            "none" is the literal string, not Python's built-in ``None``
            type.
        """,
    )
