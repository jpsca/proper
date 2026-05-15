import typing as t

from ..constants import FLASHES_SESSION_KEY, GET, HEAD
from ..errors import (
    BadRequest,
    ClientDisconnected,
    RequestEntityTooLarge,
    UnsupportedMediaType,
)
from ..helpers import DotDict, MultiDict, logger
from ..router import Route
from ..types import TReceive, TScope
from .formparser import (
    parse_json,
    parse_multipart_sync,
    parse_options_header,
    parse_query_string,
)
from .headers import RequestHeadersMixin
from .utils import make_test_scope


if t.TYPE_CHECKING:
    from ..app import App


__all__ = ("Request", )



class Request(RequestHeadersMixin):
    """An HTTP request.

    Arguments:
        scope:
            An ASGI scope dict from the server. If not provided, a test scope
            will be created.

    """

    method: str
    path: str
    form: MultiDict

    matched_route: Route | None = None
    matched_params: dict | None = None
    matched_action: str = ""

    # Cache attrs
    _query: MultiDict | None = None

    def __init__(self, scope: TScope) -> None:
        self.scope = scope or make_test_scope()
        self.form = MultiDict()
        self._session = DotDict()
        super().__init__()

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    async def _get_body(self, receive: TReceive) -> bytes:
        max_content_length = self.app.config.MAX_CONTENT_LENGTH
        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise ClientDisconnected()
            body = message.get("body", b"")
            if body:
                total += len(body)
                if max_content_length > 0 and total > max_content_length:
                    raise RequestEntityTooLarge("Maximum content length exceeded")
                chunks.append(body)
            if not message.get("more_body", False):
                break
        return b"".join(chunks)


    async def _parse_body(self, receive: TReceive) -> None:
        """Parse the request body from an ASGI receive callable."""
        if self.method in (GET, HEAD) or not self.content_length:
            return
        body = await self._get_body(receive)
        self._parse_body_bytes(body)

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

        else:
            raise UnsupportedMediaType("Unsupported Content-Type")

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
    def http_version(self) -> str:
        """The HTTP version used for the request, like "1.1"."""
        return self.scope["http_version"]

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
        qs = self.scope.get("query_string", b"")
        return qs.decode("latin-1") if isinstance(qs, bytes) else qs

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
            salt: str = "",
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

        value = self.app.loads(cookie_value, max_age=max_age, salt="cookie")

        if value is None:
            logger.info("Bad signed cookie: %s", name)
            return default
        if isinstance(value, bytes):
            return value.decode()
        return value
