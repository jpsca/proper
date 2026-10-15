import typing as t

from ...constants import FLASHES_SESSION_KEY, GET, HEAD, SIGNED_COOKIE_SALT
from ...errors import (
    BadRequest,
    RequestEntityTooLarge,
    UnsupportedMediaType,
)
from ...global_context import current
from ...helpers import DotDict, MultiDict, logger
from .formparser import (
    parse_json,
    parse_multipart_sync,
    parse_options_header,
    parse_query_string,
)
from .headers import RequestHeadersMixin


if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from ...app import App
    from ...router import Route


__all__ = ("Request", )

# How much of a body without `content-length` is read at a time.
READ_CHUNK_SIZE = 64 * 1024


class Request(RequestHeadersMixin):
    """An HTTP request.

    The server hands over the connection data already parsed; nothing here
    depends on how it arrived. The `TestClient` and the tests build these
    the same way.

    Arguments:
        method:
            The HTTP method. Uppercased.
        path:
            The path of the URL, without the query string.
        query_string:
            The part of the URL after the `?`, without it.
        headers:
            A mapping, or an iterable of `(name, value)` pairs, with the
            header names in lowercase. A header sent more than once is a
            repeated pair. A `MultiDict` becomes `request.headers` as it
            is, not a copy.
        scheme:
            `http` or `https`.
        server:
            `(host, port)` of the address the request arrived at, or `None`.
            `host` and `port` come from the `host` header, as PEP 3333
            rebuilds the URL; this address is used only without one.
        client:
            `(host, port)` of the client, or `None`.
        http_version:
            `"1.1"`, `"2"`, etc.
        server_software:
            How the server names itself, e.g. `"bearings/0.1.0"`. Empty if it
            doesn't say, or when the request doesn't come from a server.
        app:
            The app this request belongs to. Defaults to `current.app`.

    """

    method: str
    path: str
    form: MultiDict
    body: bytes

    matched_params: dict | None = None
    matched_action: str = ""
    matched_route: "Route | None" = None

    # Cache attrs
    _query: MultiDict | None = None

    def __init__(
        self,
        *,
        method: str = GET,
        path: str = "/",
        query_string: str = "",
        headers: "Mapping[str, str] | Iterable[tuple[str, str]] | None" = None,
        scheme: str = "http",
        server: "tuple[str, int | None] | None" = None,
        client: "tuple[str, int | None] | None" = None,
        http_version: str = "1.1",
        server_software: str = "",
        app: "App | None" = None,
    ) -> None:
        self._app = app
        self.method = method.upper()
        self.request_method = self.method
        self.path = path
        self._query_string = query_string
        self.scheme = scheme
        self.server = server
        self.client = client
        self.http_version = http_version
        self.server_software = server_software
        self.headers = (
            headers if type(headers) is MultiDict else MultiDict(headers or ())
        )
        self.form = MultiDict()
        self.body = b""
        self._session = DotDict()
        super().__init__()

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    def _read_body_sync(
        self, read: "Callable[[int], bytes]", *, input_terminated: bool = True
    ) -> None:
        """Read and parse the body, with `read(size)` being the server's
        blocking reader (WSGI's `wsgi.input`).

        With a `content-length`, the length is checked against
        `MAX_CONTENT_LENGTH` before a single byte is read, so an oversized
        upload is refused, not buffered. A body without one (chunked in
        HTTP/1.1, or any body in HTTP/2 and 3) is read until its end, and
        refused as soon as it passes `MAX_CONTENT_LENGTH`.

        The end of a body without a `content-length` is where `read()`
        returns `b""`, which PEP 3333 doesn't promise. A server says it
        does with `wsgi.input_terminated` (Bearings does); `input_terminated`
        is False when it doesn't, and then such a body is not read, as in
        Werkzeug.
        """
        if self._expects_body():
            self._parse_body_bytes(read(self.content_length))
        elif input_terminated and self._expects_unsized_body():
            self._parse_body_bytes(self._read_unsized_body(read))

    def _expects_body(self) -> bool:
        if self.method in (GET, HEAD) or not self.content_length:
            return False
        max_content_length = self.app.config.MAX_CONTENT_LENGTH
        if max_content_length > 0 and self.content_length > max_content_length:
            raise RequestEntityTooLarge("Maximum content length exceeded")
        return True

    def _expects_unsized_body(self) -> bool:
        """Whether there is a body without a `content-length`.

        In HTTP/1.1 that is a chunked body (`transfer-encoding`); without
        either header there is no body (RFC 9112 §6.3). HTTP/2 and 3 have
        no `transfer-encoding`: there, the `content-length` is optional.
        """
        if self.method in (GET, HEAD) or "content-length" in self.headers:
            return False
        return "transfer-encoding" in self.headers or not self.http_version.startswith(
            "1"
        )

    def _read_unsized_body(self, read: "Callable[[int], bytes]") -> bytes:
        """Read until `read()` returns `b""`, but not past `MAX_CONTENT_LENGTH`."""
        max_content_length = self.app.config.MAX_CONTENT_LENGTH
        chunks = []
        size = 0
        while True:
            want = READ_CHUNK_SIZE
            if max_content_length > 0:
                want = min(want, max_content_length + 1 - size)
            chunk = read(want)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
            if max_content_length > 0 and size > max_content_length:
                raise RequestEntityTooLarge("Maximum content length exceeded")

    def _parse_body_bytes(
        self,
        body: bytes,
        content_type: str | None = None,
        options: dict | None = None,
    ) -> None:
        """Parse already-available body bytes. Used by the test helper
        and as the shared logic for non-multipart content types.
        """
        if self.method in (GET, HEAD):
            return

        max_content_length = self.app.config.MAX_CONTENT_LENGTH
        if max_content_length > 0 and len(body) > max_content_length:
            raise RequestEntityTooLarge("Maximum content length exceeded.")
        if self.content_length and len(body) != self.content_length:
            raise BadRequest("Body size doesn't match the declared Content-Length.")
        if not body:
            return

        # Always expose the raw bytes - binary uploads (image/png PUTs,
        # etc.) have no parser but the controller still needs the body.
        self.body = body

        if content_type is None:
            content_type, options = parse_options_header(self.content_type)

        encoding = (options or {}).get("charset", "utf-8")

        if content_type == "multipart/form-data":
            config = self.app.config
            self.form = parse_multipart_sync(
                body,
                options or {},
                encoding=encoding,
                max_files=config.MAX_FORM_FILES,
                max_fields=config.MAX_FORM_FIELDS,
                max_part_size=config.MAX_FORM_PART_SIZE,
            )

        elif content_type in (
            "application/x-www-form-urlencoded",
            "application/x-url-encoded",
        ):
            text = _decode(body, encoding)
            try:
                self.form = parse_query_string(text, encoding=encoding)
            except UnicodeError:
                # The percent-escapes are decoded with the "replace" error
                # handler, which a codec such as `idna` doesn't support.
                raise UnsupportedMediaType(
                    f"Unsupported charset for a form: {encoding!r}."
                ) from None

        elif content_type.startswith("application/json"):
            self.form = parse_json(_decode(body, encoding))

        # Other content types: no parser available, but `self.body` carries
        # the raw bytes. The controller decides what to do (binary upload,
        # custom format, etc.) or just ignores them.

    @property
    def app(self) -> "App":
        return self._app or current.app

    @property
    def session(self) -> DotDict:
        return self._session

    @session.setter
    def session(self, value: dict | DotDict) -> None:
        self._session = value if isinstance(value, DotDict) else DotDict(value)

    @property
    def flashes(self) -> list[tuple[str, str]]:
        """The flashed messages stored in the session cookie."""
        return self.session.get(FLASHES_SESSION_KEY, [])

    @property
    def query(self) -> MultiDict:
        """A `MultiDict` object containing the query string data."""
        if self._query is None:
            self._query = self._parse_query()
        return self._query

    def _parse_query(self) -> MultiDict:
        return parse_query_string(
            self.query_string,
            encoding="utf-8",
            max_query_size=self.app.config.MAX_QUERY_SIZE,
        )

    @property
    def query_string(self) -> str:
        """Returns the query string."""
        return self._query_string

    @property
    def url(self) -> str:
        """Returns the current URL."""
        return self.get_url()

    def get_url(self, include_query: bool = True) -> str:
        """Returns the current URL, optionally including the query string"""
        url = self.path
        if include_query and self.query_string:
            url = f"{url}?{self.query_string}"
        return url

    def get_cookie(self, name: str, default: str | None = None) -> str | None:
        """
        Returns a cookie value for the given cookie name, or the default value
        if there is no cookie with that name.

        For example:

        $ request.get_cookie("name")
        'Jon'
        $ request.get_cookie("nonexistent-cookie")
        None
        $ request.get_cookie("nonexistent-cookie", False)
        False
    """
        cookie = self.cookies.get(name)
        if cookie is None:
            return default
        return cookie

    def get_signed_cookie(
            self,
            name: str,
            default: str | None = None,
            *,
            salt: str = SIGNED_COOKIE_SALT,
            max_age: int | None = None,
        ) -> str | t.Any:
        """
        Returns a cookie value for a signed cookie.

        Returns the default value if there is no cookie with that name or
        if the signature is no longer valid.

        The optional salt argument can be used to provide extra protection against
        brute force attacks on your secret key. If supplied, the `max_age` argument
        will be checked against the signed timestamp attached to the cookie value
        to ensure the cookie is not older than `max_age` seconds.

        For example:

        $ request.get_signed_cookie("name")
        'Jon'
        $ request.get_signed_cookie("name", salt="name-salt")
        'Jon' # assuming cookie was set using the same salt
        $ request.get_signed_cookie("nonexistent-cookie")
        None
        $ request.get_signed_cookie("nonexistent-cookie", False)
        False
        $ request.get_signed_cookie("cookie-that-was-tampered-with")
        None
        $ request.get_signed_cookie("name", max_age=60)
        None
    """
        assert self.app
        cookie_value = self.get_cookie(name)
        if cookie_value is None:
            return default

        value = self.app.loads(cookie_value, max_age=max_age, salt=salt)

        if value is None:
            logger.info("Bad signed cookie: %s", name)
            return default
        if isinstance(value, bytes):
            return value.decode()
        return value


def _decode(body: bytes, encoding: str) -> str:
    """Decode a urlencoded or JSON body with the charset of its
    `content-type`.

    An unknown charset is a 415; bytes that aren't valid in that charset
    are a 400. A charset name that Python can't look up at all (one with a
    NUL, which RFC 2231 decoding gives for `charset*=utf-8''utf-8%00`)
    raises `ValueError`, and is an unknown charset too.
    """
    try:
        return body.decode(encoding)
    except UnicodeError:
        raise BadRequest(f"The body is not valid {encoding}.") from None
    except LookupError, ValueError:
        # `UnicodeError` is a `ValueError`, so it is caught first.
        raise UnsupportedMediaType(f"Unknown charset: {encoding!r}.") from None
