import typing as t

from ...constants import FLASHES_SESSION_KEY, GET, HEAD, SIGNED_COOKIE_SALT
from ...errors import (
    BadRequest,
    RequestEntityTooLarge,
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
    from collections.abc import Awaitable, Callable, Iterable, Mapping

    from ...app import App
    from ...router import Route

    TReadBody = Callable[[], Awaitable[bytes]]


__all__ = ("Request", )



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
            repeated pair.
        scheme:
            `http` or `https`.
        server:
            `(host, port)` of the address the request arrived at, or `None`
            to take it from the `host` header.
        client:
            `(host, port)` of the client, or `None`.
        http_version:
            `"1.1"`, `"2"`, etc.
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
        if headers is None:
            self.headers = MultiDict()
        elif hasattr(headers, "items"):
            self.headers = MultiDict(headers.items())  # type: ignore[union-attr]
        else:
            self.headers = MultiDict(headers)
        self.form = MultiDict()
        self.body = b""
        self._session = DotDict()
        super().__init__()

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    async def _read_body(self, read: "TReadBody") -> None:
        """Read and parse the body, with `read()` being the server's
        awaitable that returns the whole body as bytes.

        Requests without a `content-length` carry no body for us: the
        length is checked against `MAX_CONTENT_LENGTH` before a single
        byte is read, so an oversized upload is refused, not buffered.
        """
        if self._expects_body():
            self._parse_body_bytes(await read())

    def _read_body_sync(self, read: "Callable[[int], bytes]") -> None:
        """`_read_body` for a server that hands us a blocking `read(size)`,
        like WSGI's `wsgi.input`."""
        if self._expects_body():
            self._parse_body_bytes(read(self.content_length))

    def _expects_body(self) -> bool:
        if self.method in (GET, HEAD) or not self.content_length:
            return False
        max_content_length = self.app.config.MAX_CONTENT_LENGTH
        if max_content_length > 0 and self.content_length > max_content_length:
            raise RequestEntityTooLarge("Maximum content length exceeded")
        return True

    def _parse_body_bytes(
        self,
        body: bytes,
        content_type: str | None = None,
        options: dict | None = None,
    ) -> None:
        """Parse already-available body bytes. Used by the test helper
        and as the shared logic for non-multipart content types.
        """
        if self.method in (GET, HEAD) or not self.content_length:
            return

        max_content_length = self.app.config.MAX_CONTENT_LENGTH
        if max_content_length > 0 and len(body) > max_content_length:
            raise RequestEntityTooLarge("Maximum content length exceeded.")
        if len(body) != self.content_length:
            raise BadRequest("Body size doesn't match the declared Content-Length.")

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
            self.form = parse_query_string(body.decode(encoding), encoding=encoding)

        elif content_type.startswith("application/json"):
            self.form = parse_json(body.decode(encoding))

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
        self._session = DotDict(value)

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
