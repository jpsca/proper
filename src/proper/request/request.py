import mimetypes
import typing as t
from io import BytesIO
from types import MappingProxyType
from wsgiref.util import request_uri

from proper.constants import DELETE, FLASHES_SESSION_KEY, GET, HEAD, PATCH, POST, PUT
from proper.errors import InvalidHeader
from proper.helpers import MultiDict, tunnel_decode, tunnel_encode
from proper.router import Route

from .headers import RequestHeaders
from .parse_form_data import parse_form_data, parse_query_string


__all__ = ("Request", "make_test_env")

DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
MIME_ALL = "*/*"
DEFAULT_FORMAT = "html"


class Request:
    """An HTTP request.

    Any attribute not listed here is searched in the headers dict,
    so, for example, `request.if_modified_since` is the same as
    `request.headers["if_modified_since"]`.

    Args:
        encoding: Default encoding.
        max_content_length
        max_query_size
        **env: A WSGI environment dict passed in from the
            server (See also PEP-3333).

    Attributes:
        env:
            The WSGI environment dict passed in from the server.
        body:
            The request body as a BytesIO stream.
        content_length:
            The length in bytes, as an integer, of the content
            sent by the client.
        content_type:
            The MIME content type of the incoming request.
        cookies:
            A dict with the cookies sent with the request.
        default_port:
            Returns the default port (80 for HTTP, 443 for HTTPS)
        encoding:
            From the arguments.
        flashes:
            The flashed messages stored in the session cookie.
            By reading this value it will be stored in the request but
            deleted form the session.
        form:
            A `MultiDict` object containing the parsed body data, like the
            one sent by a HTML form with a POST, **including** the files.
        format:
            Computed based on the value of the "Accept" header, with "html"
            as a fallback.
        headers:
            The complete set of HTTP headers
        host_with_port:
            A host:port string for this request. The port is not included
            if its the default for the protocol.
        is_get, is_head, is_post, is_put, is_patch, and is_delete:
            Return True or False based on the request method.
        is_ssl:
            Whether the current request was made via a SSL connection.
        is_xhr:
            True if current request is an XHR request.
        max_content_length:
            From the arguments.
        max_query_size:
            From the arguments.
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
        protocol, host, port, path, and query_string:
            Components of the URL used for the request, based on the pattern:
            `protocol://host:port/path?query_string`.
        query:
            A `MultiDict` object containing the query string data.
        remote_ip:
            IP address of the closest client or proxy to the WSGI server.
            If your application is behind one or more reverse proxies,
            and it doesn't pass forward the IP address of the client,
            you can use the `access_route` attribute to retrieve the real
            IP address of the client.
        request_method:
            The uppercased request method, like: "GET".
        session:
            The session data sent with the request.
        url:
            Returns the full URL used for the request.

    Extra attributes:
        request_id:
        matched_route:
        matched_params:
        matched_action:
        user:
        csrf_token:

    """

    request_id: str = ""
    matched_route: Route | None = None
    matched_params: dict | None = None
    matched_action: str | None = None
    user: t.Any = None
    csrf_token: str | None = None

    # Cache attrs
    _form: MultiDict | None = None
    _format: str | None = None
    _query: MultiDict | None = None

    def __init__(
        self,
        *,
        encoding: str = "utf8",
        max_content_length: int = -1,
        max_query_size: int | None = None,
        **env,
    ) -> None:
        env = env or make_test_env()
        headers = {}
        for key in list(env.keys()):
            if key.startswith("HTTP_"):
                name = key.strip().lower().replace("-", "_").removeprefix("http_")
                headers[name] = env.pop(key, None)

        self.env = env
        self.headers = RequestHeaders(headers)

        self.encoding = encoding
        self.max_content_length = max_content_length
        self.max_query_size = max_query_size

        self.method = env.get("REQUEST_METHOD", GET).upper()
        self.request_method = self.method

        # PATH_INFO is always "bytes tunneled as latin-1" and must be decoded back.
        self.path = "/" + tunnel_decode(env.get("PATH_INFO", "").strip("/"))

        self.content_type = env.get("CONTENT_TYPE", "")
        self.protocol = self.headers["forwarded_proto"] or env.get(
            "wsgi.url_protocol"
        )

        try:
            self.content_length = int(env.get("CONTENT_LENGTH", "0"))
        except ValueError:
            raise InvalidHeader("The Content-Length header must be a number.")
        if self.content_length < 0:
            raise InvalidHeader(
                "The value of the Content-Length header must be a positive number."
            )

        host, port = self.headers["host"]
        self.host = host
        self.port = port or self.default_port

        self._session = MappingProxyType({})

    def __getattribute__(self, key) -> t.Any:
        return self.headers.get(key)

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    @property
    def body(self) -> BytesIO:
        return self.env.get("wsgi.input") or BytesIO()

    @property
    def cookies(self) -> dict:
        return self.headers["cookie"]

    @property
    def default_port(self) -> int:
        return DEFAULT_HTTPS_PORT if self.protocol == "https" else DEFAULT_HTTP_PORT

    @property
    def flashes(self) -> dict:
        return self._session.get(FLASHES_SESSION_KEY, {})

    @property
    def form(self) -> MultiDict:
        if self._form is None:
            self._form = self._parse_form()
        return self._form

    def _parse_form(self) -> MultiDict:
        # GET and HEAD can't have form data.
        if self.method in (GET, HEAD):
            return MultiDict()

        return parse_form_data(
            self.body,
            self.content_type,
            self.content_length,
            encoding=self.encoding,
            max_content_length=self.max_content_length,
        )

    @property
    def format(self) -> str:
        if self._format is None:
            self._format = self._parse_format()
        return self._format

    def _parse_format(self) -> str:
        format_ = None
        for mime in self.accept:
            if mime == MIME_ALL:
                break
            ext = mimetypes.guess_extension(mime)
            if ext:
                format_ = ext[1:]
                break

        return format_ or DEFAULT_FORMAT

    @property
    def host_with_port(self) -> str:
        """Returns a host:port string for this request, such as “example.com” or
        “example.com:8080”.
        Port is only included if it is not a default port (80 or 443)
        """
        return f"{self.host}{self.port_string}"

    @property
    def is_delete(self) -> bool:
        return self.method == DELETE

    @property
    def is_get(self) -> bool:
        return self.method == GET

    @property
    def is_head(self) -> bool:
        return self.request_method == HEAD

    @property
    def is_patch(self) -> bool:
        return self.method == PATCH

    @property
    def is_post(self) -> bool:
        return self.method == POST

    @property
    def is_put(self) -> bool:
        return self.method == PUT

    @property
    def is_ssl(self) -> bool:
        return self.protocol == "https"

    @property
    def is_xhr(self) -> bool:
        return self.headers["x_requested_with"] == "XMLHttpRequest"

    @property
    def port_is_default(self) -> bool:
        return self.port == self.default_port

    @property
    def port_string(self) -> str:
        return "" if self.port_is_default else f":{self.port}"

    @property
    def query(self) -> MultiDict:
        if self._query is None:
            self._query = self._parse_query()
        return self._query

    def _parse_query(self) -> MultiDict:
        return parse_query_string(
            self.query_string,
            encoding=self.encoding,
            max_query_size=self.max_query_size,
        )

    @property
    def query_string(self) -> str:
        return self.env.get("QUERY_STRING", "")

    @property
    def remote_ip(self) -> str:
        """Passed-forward IP address of the client or IP address of the
        closest proxy to the WSGI server.
        """
        return (
            self.headers["x_forwarded_for"]
            or self.headers["x_real_ip"]
            or self.env.get("REMOTE_ADDR")
            or "127.0.0.1"
        )

    @property
    def session(self) -> MappingProxyType:
        return self._session

    @property
    def url(self) -> str:
        """Returns the current URL."""
        return request_uri(self.env, include_query=True)


def make_test_env(path: str = "", **kw) -> dict:
    from wsgiref.util import setup_testing_defaults

    env = {"REMOTE_ADDR": "127.0.0.1"}
    setup_testing_defaults(env)

    if path:
        if "?" in path:
            path, query = path.rsplit("?", 1)
            env["QUERY_STRING"] = query
        env["PATH_INFO"] = tunnel_encode(path.strip())

    env.update({key: str(value) for key, value in kw.items()})
    return env
