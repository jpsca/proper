import typing as t

import itsdangerous

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

    Attributes:

        scope:
            The ASGI scope dict passed in from the server.

        query:
            A `MultiDict` object containing the query string data.

        form:
            A `MultiDict` object containing the parsed body data, like the
            one sent by a HTML form with a POST, **including** the files.

        accept:
            Parsed "accept" header, if present.
            Indicates which content types, expressed as MIME types, the client
            is able to understand.

        accept_encoding:
            Parsed "accept-encoding" header, if present.
            Indicates the content encoding (usually a compression algorithm) that
            the client can understand.

        accept_language:
            Parsed "accept-language" header, if present.
            Indicates the natural language and locale that the client prefers.

        content_length:
            The length in bytes, as an integer, of the content
            sent by the client.

        content_type:
            The MIME content type of the incoming request.

        cookies:
            A dict with the cookies sent with the request.

        date:
            Parsed "date" header, if present.
            Indicates the date and time at which the message was originated.

        default_port:
            Returns the default port (80 for HTTP, 443 for HTTPS)

        encoding:
            From the arguments.

        flashes:
            The flashed messages stored in the session cookie.
            By reading this value it will be stored in the request but
            deleted from the session.

        format:
            Computed based on the value of the "accept" header, with "html"
            as a fallback.

        forwarded:
            A comma-separated list of forwarding information from the client
            to the server on its way through proxies.

        host, protocol, port, path, and query_string:
            Components of the URL used for the request, based on the pattern:
            `protocol://host:port/path?query_string`.

        host_with_port:
            A host:port string for this request. The port is not included
            if its the default for the protocol.

        if_none_match:
            A list of ETags provided by the client.

        if_modified_since:
            The date and time at which the client last modified the resource.

        is_get, is_head, is_post, is_put, is_patch, and is_delete:
            Return True or False based on the request method.

        is_secure/is_ssl:
            Whether the current request was made via a HTTPS connection.

        is_xhr:
            True if current request is an XHR request.

        max_content_length:
            From the arguments.

        max_query_size:
            From the arguments.

        request_method:
            The uppercased request method, like: "GET".

        method:
            Returns the same value as `request_method` except for HEAD,
            which it returns as GET; or for POST if it has been overrided
            by PATCH, PUT, or DELETE (see `Method override`).

        port_is_default:
            Returns True or False, depending if the port is the default for
            the protocol.

        port_string:
            A `:port` string for the request if the port is not the default for
            the protocol.

        remote_ip:
            IP address of the closest client or proxy to the WSGI server.
            This will use the `forwarded` header to try to found the real
            IP address of the client if your application is behind one or
            more reverse proxies,

        request_id:
            Parse the `x-request-id` header for a value that uniquely
            identify a request.

        session:
            The session data sent with the request.

        url:
            Returns the full URL used for the request.

        matched_route, matched_params, and matched_action:
            Added when the request match a route.

    """

    method: str
    path: str
    form: MultiDict

    matched_route: Route | None = None
    matched_params: dict | None = None
    matched_action: str | None = None

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
        serializer = self.app.get_serializer(salt)
        cookie_value = self.get_cookie(name)
        if cookie_value is None:
            return default

        try:
            value = serializer.loads(cookie_value, max_age=max_age)
            if isinstance(value, bytes):
                return value.decode()
            else:
                return value

        except itsdangerous.BadSignature:
            logger.info("Bad signed cookie: %s", name)
            return default
