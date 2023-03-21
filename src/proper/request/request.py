import typing as t
from io import BytesIO
from types import MappingProxyType
from wsgiref.util import request_uri

from proper.constants import FLASHES_SESSION_KEY, GET, HEAD
from proper.helpers import MultiDict, tunnel_encode
from proper.router import Route

from .headers import RequestHeadersMixin
from .parse_form_data import parse_form_data, parse_query_string


__all__ = ("Request", "make_test_env")


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


class Request(RequestHeadersMixin):
    """An HTTP request.

    Args:
        encoding:
            Default encoding.

        max_content_length:

        max_query_size:

        **env:
            A WSGI environment dict passed in from the server
            (See also PEP-3333).

    Attributes:
        env:
            The WSGI environment dict passed in from the server.

        body:
            The request body as a BytesIO stream.

        accept:
            Indicates which content types, expressed as MIME types,
            the client is able to understand.

        accept_encoding:
            Indicates the content encoding (usually a compression algorithm) that
            the client can understand.

        accept_language:
            Indicates the natural language and locale that the client prefers.

        content_length:
            The length in bytes, as an integer, of the content
            sent by the client.

        content_type:
            The MIME content type of the incoming request.

        cookies:
            A dict with the cookies sent with the request.

        date:
            The date and time at which the message originated.

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

        forwarded:
            A comma-separated list of forwarding information from the client
            to the server on its way through proxies.

        host, protocol, port, path, and query_string:
            Components of the URL used for the request, based on the pattern:
            `protocol://host:port/path?query_string`.

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

        query:
            A `MultiDict` object containing the query string data.

        remote_ip:
            IP address of the closest client or proxy to the WSGI server.
            If your application is behind one or more reverse proxies,
            and it doesn't pass forward the IP address of the client,
            you can use the `access_route` attribute to retrieve the real
            IP address of the client.

        request_id:
            Parse the `x-request-id` header for a value that uniquely
            identify a request.

        session:
            The session data sent with the request.

        url:
            Returns the full URL used for the request.

    Extra attributes:
        matched_route:
        matched_params:
        matched_action:
        user:
        csrf_token:

    """
    method: str
    path: str

    request_id: str = ""
    matched_route: Route | None = None
    matched_params: dict | None = None
    matched_action: str | None = None
    user: t.Any = None
    csrf_token: str | None = None

    # Cache attrs
    _form: MultiDict | None = None
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
        self.env = env

        self.encoding = encoding
        self.max_content_length = max_content_length
        self.max_query_size = max_query_size

        self._session = MappingProxyType({})

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    @property
    def body(self) -> BytesIO:
        return self.env.get("wsgi.input") or BytesIO()

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
    def session(self) -> MappingProxyType:
        return self._session

    @property
    def url(self) -> str:
        """Returns the current URL."""
        return request_uri(self.env, include_query=True)
