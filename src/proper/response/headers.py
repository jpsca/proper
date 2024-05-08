import typing as t
from datetime import date, datetime
from hashlib import sha1

from proper.errors import InvalidHeader
from proper.helpers import format_http_date, tunnel_encode


def enc_name(name: str) -> str:
    name = name.strip().lower().removeprefix("http_").replace("_", "-")
    if not name.isascii():
        raise InvalidHeader("A header name must be encodable as latin-1")
    return name


class ResponseHeadersDict(dict):
    def __getitem__(self, name: str) -> t.Any:
        name = enc_name(name)
        return dict.get(self, name)

    def __setitem__(self, name: str, val: t.Any) -> None:
        self.set(name, val)

    def _set(self, name: str, coded_val: t.Any) -> None:
        if coded_val is None:
            if name in self:
                del self[name]
        else:
            dict.__setitem__(self, name, coded_val)

    def set(self, name: str, val: t.Any, **params) -> None:
        name = enc_name(name)
        self._set(name, format_header(val, **params))

    def setdefault(self, name: str, val: t.Any, **params) -> None:
        if name in self:
            return
        self.set(name, val, **params)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v


class ResponseHeadersMixin:
    """Mixin with the methods related to the response headers."""

    default_mimetype = "text/html"
    default_charset = "utf-8"

    # Header exclude-list for specific response codes
    # (rfc2616 section 10.2.3 and 10.3.5)
    exclude_headers = {
        204: ("content-type", "content-length"),
        304: (
            "allow",
            "content-encoding",
            "content-language",
            "content-length",
            "content-range",
            "content-type",
            "content-md5",
            "last-modified",
        ),
    }

    headers: ResponseHeadersDict

    def __init__(self) -> None:
        self.headers = ResponseHeadersDict()
        self._mimetype = self.default_mimetype
        self._charset = self.default_charset
        self.set_content_type(self.mimetype, charset=self.charset)
        super().__init__()

    @property
    def status_code(self) -> int:
        raise NotImplementedError

    @property
    def accept_ranges(self) -> str | None:
        """Get the `Accept-Ranges` header."""
        return self.headers.get("accept-ranges")

    @accept_ranges.setter
    def accept_ranges(self, unit: str | None = "bytes") -> None:
        self.set_accept_ranges(unit)

    def set_accept_ranges(self, unit: str | None = "bytes") -> None:
        """Set the `Accept-Ranges` header.

        The Accept-Ranges HTTP response header is a marker used by the
        server to advertise its support for partial requests from the
        client for file downloads. The value of this field indicates
        the unit that can be used to define a range.

        In the presence of an Accept-Ranges header, the browser may
        try to resume an interrupted download instead of trying to
        restart the download.

        Arguments:

            unit:
                The default is `'bytes'` - the only range unit formally
                defined by [RFC 7233](https://datatracker.ietf.org/doc/html/rfc7233).
                Use `None` to delete the header.

        """
        self.headers._set("accept-ranges", unit)

    @property
    def cache_control(self) -> list[str] | None:
        """Get the `Cache-Control` header."""
        return self.headers.get("cache-control")

    @cache_control.setter
    def cache_control(self, directives: list[str] | None) -> None:
        if directives:
            self.set_cache_control(*directives)
        else:
            self.set_cache_control()

    def set_cache_control(self, *directives: str) -> None:
        """Set the `Cache-Control` header.

        The Cache-Control HTTP header field holds "directives" (instructions)
        that control caching in browsers and shared caches (e.g. Proxies, CDNs).

        Arguments:

            *directives:
                list of cache directives that are joined with ", "
                to produce the value for the header.
                Pass zero directives to delete the header.

        """
        self.headers._set(
            "cache-control",
            format_comma_list(*directives) if directives else None,
        )

    @property
    def content_encoding(self) -> str | None:
        """Get the `Content-Encoding` header."""
        return self.headers.get("content-encoding")

    @content_encoding.setter
    def content_encoding(self, values: list[str] | None) -> None:
        if values:
            self.set_content_encoding(*values)
        else:
            self.set_content_encoding()

    def set_content_encoding(self, *values: str) -> None:
        """Set the `Content-Encoding` header.

        Lists any encodings that have been applied to the body
        and in what order. This lets the recipient know how to decode
        the representation in order to obtain the original format.

        Content encoding is mainly used to compress the message data
        without losing information about the origin media type.

        Arguments:

            *values:
                Lists any encodings that have been applied to the body
                in what order
                Pass zero values to delete the header.

        """
        self.headers._set(
            "content-encoding",
            format_comma_list(*values) if values else None,
        )

    @property
    def content_length(self) -> str | None:
        """Get the `Content-Length` header."""
        return self.headers.get("content-length")

    @content_length.setter
    def content_length(self, num: int | str | None) -> None:
        self.set_content_length(num)

    def set_content_length(self, num: int | str | None) -> None:
        """Set the `Content-Length` header.

        This property can be used when streaming the response.
        When the response has content, the framework will force
        Content-Length to be the length of the given text bytes.

        Arguments:

            num:
                Number of bytes of the returned content.
                Use `None` to delete the header.

        """
        self.headers._set("content-length", format_int(num))

    @property
    def content_location(self) -> str | None:
        """Get the `Content-Location` header."""
        return self.headers.get("content-location")

    @content_location.setter
    def content_location(self, url: str | None) -> None:
        self.set_content_location(url)

    def set_content_location(self, url: str | None) -> None:
        """Set the `Content-Location` header.

        The Content-Location header indicates an *alternate location*
        for the returned data. The principal use is to indicate the
        URL of a resource transmitted as the result of content negotiation.

        Do not mistake this header with `Location`, that is used
        for redirects.

        Arguments:

            url:
                Use `None` to delete the header.

        """
        self.headers._set("content-location", url)

    @property
    def content_range(self) -> str | None:
        """Get the `Content-Range` header."""
        return self.headers.get("content-range")

    def set_content_range(
        self,
        unit: str | None = "bytes",
        *,
        start: int | None = None,
        end: int | None = None,
        size: int | None = None,
    ) -> None:
        """Set the `Content-Range ` header.

        The Content-Range response HTTP header indicates where in a
        full body message a partial message belongs.

        Arguments:

            unit:
                The unit in which ranges are specified,`'bytes'` by default.
                Use `None` to delete the header.

            start:
                An integer in the given unit indicating the start position
                (zero-indexed & inclusive) of the request range.

            end:
                An integer in the given unit indicating the end position
                (zero-indexed & inclusive) of the requested range.

            size:
                The total length of the document.

        Examples:

            ```python
            resp.set_content_range("bytes", start=123, end=456, size=7890)
            # 'Content-Range: bytes 123-456/7890'

            resp.set_content_range(start=123, end=456)
            # Content-Range: bytes 123-456/*

            resp.set_content_range(size=7890)
            # Content-Range: bytes */7890
            ```

        """
        if unit is None:
            val = None
        else:
            if start is None or end is None:
                range = "*"
            else:
                range = f"{start}-{end}"
            val = f"{unit} {range}/{size or '*'}"

        self.headers._set("content-range", val)

    @property
    def mimetype(self) -> str:
        return self._mimetype or ""

    @mimetype.setter
    def mimetype(self, val: str) -> None:
        self.set_content_type(mimetype=val, charset=self._charset)

    @property
    def charset(self) -> str:
        return self._charset or ""

    @charset.setter
    def charset(self, val: str) -> None:
        self.set_content_type(mimetype=self.mimetype, charset=val)

    @property
    def content_type(self) -> str | None:
        """Get the `Content-Type` header."""
        return self.headers.get("content-type")

    @content_type.setter
    def content_type(self, val: str) -> None:
        self.set_content_type(mimetype=val, charset=self._charset)

    def set_content_type(self, mimetype: str, charset: str) -> None:
        """Set the `Content-Type` header.

        The Content-Type header is used to indicate the original media
        type of the resource (prior to any content encoding applied
        for sending).

        Arguments:

            val:
                `text/html` by default
                Use `None` to delete the header.

            charset:
                "utf-8" by default

        """
        self._mimetype = mimetype
        self._charset = charset
        self.headers._set("content-type", format_header(mimetype, charset=charset))

    @property
    def etag(self) -> str | None:
        """Get the ETag header."""
        return self.headers.get("etag")

    def set_etag(
        self,
        val: date | int | float | str | None,
        *,
        strong: bool = False,
    ) -> None:
        """Set the ETag header.

        The ETag (or entity tag) HTTP response header is an identifier for a
        specific version of a resource. It lets caches be more efficient and
        save bandwidth, as a web server does not need to resend a full response
        if the content was not changed.

        Arguments:

            val:
                The ETag can be generated from a date, a number or a string that
                represents the "version" or the content: a date, number, tag, etc.
                This value is sha1-hashed to generate the final one.
                Use `None` to delete the header.

            strong:
                By default a “weak” ETag is used. Set this to `True` to set a
                “strong” ETag validator on the response. A strong ETag implies
                exact equality: the response must match byte for byte.
                This is necessary for doing range requests within a large file
                or for compatibility with some CDNs that don’t support weak ETags.

        """
        coded_val = None
        if val is not None:
            # not md5 because is not availabe in some systems
            digest = sha1(str(val).encode()).hexdigest()
            coded_val = f'"{digest}"' if strong else f'W/"{digest}"'

        self.headers._set("etag", coded_val)

    @property
    def expires(self) -> str | None:
        """Get the `Expires` header."""
        return self.headers.get("expires")

    @expires.setter
    def expires(self, dt: datetime | float | int | None) -> None:
        self.set_expires(dt)

    def set_expires(self, dt: datetime | float | int | None) -> None:
        """Set the `Expires` header.

        The Expires HTTP header contains the datetime after whic
        the response is considered expired.

        Arguments:

            dt:
                The header can be generated from a timestamp or an
                UTC or naive datetime.
                Use `None` to delete the header.

        """
        self.headers._set("expires", format_datetime(dt))

    @property
    def last_modified(self) -> datetime | None:
        """Get the `Last-Modified` header."""
        return self.headers.get("last-modified")

    @last_modified.setter
    def last_modified(self, dt: datetime | float | int | None) -> None:
        self.set_last_modified(dt)

    def set_last_modified(self, dt: datetime | float | int | None) -> None:
        """Set the `Last-Modified` header.

        The Last-Modified response HTTP header contains a date and time
        when the origin server believes the resource was last modified.
        It is used as a validator to determine if the resource is the same
        as the previously stored one. Less accurate than an ETag header,
        it is a fallback mechanism.

        Conditional requests containing If-Modified-Since or If-Unmodified-Since
        headers make use of this field.

        Last-Modified is also used by crawlers to adjust crawl frequency,
        by browsers in heuristic caching, and by content management systems (CMS)
        to display the time the content was last modified.

        Arguments:

            dt:
                The header can be generated from a timestamp or an
                UTC or naive datetime.
                Use `None` to delete the header.

        """
        self.headers._set("last-modified", format_datetime(dt))

    @property
    def location(self) -> str | None:
        """Get the `Location` header."""
        return self.headers.get("location")

    @location.setter
    def location(self, url: str | None) -> None:
        self.set_location(url)

    def set_location(self, url: str | None) -> None:
        """Set the `Location` header.

        The Location response header indicates the URL to redirect a page to.
        It only provides a meaning when served with a 3xx (redirection)
        or 201 (created) status response.

        In cases of redirection, the HTTP method used to make the new request
        to fetch the page pointed to by Location depends on the original method
        and the kind of redirection:

        - `303 See Other` responses always lead to the use of a GET method.
        - `307 Temporary Redirect` and `308 Permanent Redirect` don't change
            the method used in the original request.
        - `301 Moved Permanently` and `302 Found` don't change the method most
            of the time, though older user-agents may.

        All responses with one of these status codes send a Location header.

        In cases of resource creation, it indicates the URL to the newly
        created resource.

        Arguments:

            url:
                The URL of the resource.
                Use `None` to delete the header.

        """
        self.headers._set("location", url)

    @property
    def retry_after(self) -> str | None:
        """Get the `Retry-After` header."""
        return self.headers.get("retry-after")

    @retry_after.setter
    def retry_after(self, num: int | str | None) -> None:
        self.set_retry_after(num)

    def set_retry_after(self, num: int | str | None) -> None:
        """Set the Retry-After header.

        The Retry-After response HTTP header indicates how long the user agent
        should wait before making a follow-up request.

        There are three main cases this header is used:

        - When sent with a `503 Service Unavailable` response, this indicates how
            long the service is expected to be unavailable.
        - When sent with a `429 Too Many Requests` response, this indicates how long
            to wait before making a new request.
        - When sent with a redirect response, such as `301 Moved Permanently`,
            this indicates the minimum time that the user agent is asked to wait
            before issuing the redirected request.

        Arguments:

            num:
                The expected value is an integral number of seconds.
                The HTTP-date syntax is not supported.
                Use `None` to delete the header.

        """
        if num is not None:
            # num=0 is the same as num=None
            num = int(num) or None
        self.headers._set("retry-after", num)

    @property
    def vary(self) -> str | None:
        """Get the `Vary` header."""
        return self.headers.get("vary")

    @vary.setter
    def vary(self, names: list[str] | None) -> None:
        if names:
            self.set_vary(*names)
        else:
            self.set_vary()

    def set_vary(self, *names: str) -> None:
        """Set the `Vary` header.

        The Vary HTTP response header describes the parts of the request message
        aside from the method and URL that influenced the content of the response
        it occurs in. Most often, this is used to create a cache key when
        content negotiation is in use.

        The same Vary header value should be used on all responses for a given URL
        including 304 Not Modified responses.

        Arguments:

            *names:
                One or more header names.
                Pass zero names to delete the header.

        """
        self.headers._set(
            "vary",
            format_comma_list(*names) if names else None,
        )

    def _get_header_tuples(self) -> list[tuple[str, str]]:
        """Get the list of header tuples."""
        exclude = self.exclude_headers.get(self.status_code) or []
        tuples = []

        for name, val in self.headers.items():
            if name in exclude:
                continue

            if isinstance(val, datetime):
                coded_val = format_http_date(val)
            elif isinstance(val, list):
                coded_val = ", ".join(val)
            else:
                coded_val = str(val)

            tuples.append(
                (
                    tunnel_encode(name),
                    tunnel_encode(coded_val, "utf-8"),
                )
            )

        return tuples


# --- Formatters -----


def format_datetime(dt: datetime | float | int | None) -> datetime | None:
    if dt is None:
        return None

    if isinstance(dt, (float, int)):
        dt = datetime.utcfromtimestamp(dt)

    return dt


def format_comma_list(*names: str) -> list[str] | None:
    return [str(val) for val in names]


def format_int(num: int | str | None) -> int | None:
    if num is None:
        return None

    return int(num) if num else None


def format_header(val: t.Any, **params) -> str | None:
    if val is None:
        return None

    return "; ".join(
        [
            val,
            *(f"{k}={v}" for k, v in params.items() if v),
        ]
    )
