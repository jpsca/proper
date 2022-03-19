"""
Request class.
"""
import mimetypes
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

from .. import errors
from ..constants import DELETE, FLASHES_SESSION_KEY, GET, HEAD, PATCH, POST, PUT
from ..helpers import HeadersDict, MultiDict, tunnel_decode, tunnel_encode
from ..router import Route
from .parse_accept_header import parse_accept_header
from .parse_comma_separated import parse_comma_separated
from .parse_cookies import parse_cookies
from .parse_form_data import parse_form_data
from .parse_host import parse_host
from .parse_http_date import parse_http_date
from .parse_query_string import parse_query_string


__all__ = ("Request", "make_test_environ")

DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
MIME_ALL = "*/*"
DEFAULT_FORMAT = "html"


class Request:
    """An HTTP request.

    Arguments are:

    - encoding:
        Default encoding.

    - max_content_length:

    - max_query_size:

    - **environ:
        A WSGI environment dict passed in from the server (See also PEP-3333).


    Attributes:

    - request_method:
        The uppercased request method, like: "GET".

    - method:
        Returns the same value as `request_method` except for HEAD,
        which it returns as GET; or for POST if it has been overrided
        by PATCH, PUT, or DELETE (see `Method override`).

    - is_get, is_head, is_post, is_put, is_patch, and is_delete:
        Return True or False based on the request method.

    - is_xhr:
        True if current request is an XHR request.

    - url:
        Returns the full URL used for the request.

    - protocol, host, port, path, and query_string:
        Components of the URL used for the request, based on the pattern:
        `protocol://host:port/path?query_string`.

    - host_with_port:
        A host:port string for this request. The port is not included
        if its the default for the protocol.

    - port_string:
        A `:port` string for the request if the port is not the default for
        the protocol.

    - port_is_default
        Returns True or False, depending if the port is the default for
        the protocol.

    - default_port:
        Returns the default port (80 for HTTP, 443 for HTTPS)

    - is_ssl:
        Whether the current request was made via a SSL connection.

    - remote_ip:
        IP address of the closest client or proxy to the WSGI server.

        If your application is behind one or more reverse proxies,
        and it doesn't pass forward the IP address of the client,
        you can use the `access_route` attribute to retrieve the real
        IP address of the client.

    - env:
        The WSGI environment dict passed in from the server.

    - content_type:
        The MIME content type of the incoming request.

    - content_length:
        The length in bytes, as an integer, of the content sent by the client.

    - headers:
        The complete set of HTTP headers, as a Dot dict.

    - accepts:
        A sorted list of the MIME types in the "Accept" header.

    - format:
        Computed based on the value of the "Accept" header, with "html"
        as a fallback.

    - if_none_match:
        Value of the "If-None-Match" header, as a parsed list of strings,
        or an empty list if the header is missing or its value is blank.

    - if_modified_since:
        Value of the "If-Modified-Since" header, or an empty string if the header
        is missing or the date cannot be parsed.

    - languages:
        A sorted list of the languages from the "Accept-Languages" header.

    - body:
        The request body as a BytesIO stream.

    - query:
        A `MultiDict` object containing the query string data.

    - form:
        A `MultiDict` object containing the parsed body data, like the
        one sent by a HTML form with a POST, **including** the files.

    - cookies:
        All cookies sent with the request.

    - session:
        The session data sent with the request.

    - flashes:
        The flashed messages stored in the session cookie.
        By reading this value it will be stored in the request but
        deleted form the session.

    """

    encoding: str
    max_content_length: Optional[int]
    max_query_size: Optional[int]
    env: Dict[str, Any]
    method: str
    request_method: str
    path: str
    content_type: str
    protocol: str
    host: str
    port: int

    matched_route: Optional[Route] = None
    matched_params: Optional[Dict[str, Any]] = None
    matched_action: Optional[str] = None
    user: Optional[Any] = None
    csrf_token: Optional[str] = None

    _remote_ip: Optional[str] = None
    _content_length: Optional[int] = None
    _headers: Optional[HeadersDict] = None
    _accepts: Optional[List[str]] = None
    _format: Optional[str] = None
    _if_none_match: Optional[List[str]] = None
    _if_modified_since: Optional[Union[datetime, str]] = None
    _languages: Optional[List[str]] = None
    _query: Optional[MultiDict] = None
    _form: Optional[MultiDict] = None
    _cookies: Optional[Dict[str, Any]] = None
    _session: Dict[str, Any]

    def __init__(
        self,
        *,
        encoding: str = "utf8",
        max_content_length: Optional[int] = None,
        max_query_size: Optional[int] = None,
        **env,
    ) -> None:
        self.encoding = encoding
        self.max_content_length = max_content_length
        self.max_query_size = max_query_size
        env = env or make_test_environ()
        self.env = env
        self.method = env.get("REQUEST_METHOD", "GET").upper()
        self.request_method = self.method
        # PATH_INFO is always "bytes tunneled as latin-1" and must be decoded back.
        # Read the docstring on `support/encoding.py` for more details.
        self.path = "/" + tunnel_decode(env.get("PATH_INFO", "").strip("/"))
        self.content_type = self.env.get("CONTENT_TYPE", "")
        self.protocol = self.env.get("HTTP_X_FORWARDED_PROTO") or self.env.get(
            "wsgi.url_protocol"
        )
        self.host, self.port = parse_host(self.env.get("HTTP_HOST"), self.default_port)
        self._session = {}

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    @property
    def is_get(self) -> bool:
        return self.method == GET

    @property
    def is_head(self) -> bool:
        return self.request_method == HEAD

    @property
    def is_post(self) -> bool:
        return self.method == POST

    @property
    def is_put(self) -> bool:
        return self.method == PUT

    @property
    def is_patch(self) -> bool:
        return self.method == PATCH

    @property
    def is_delete(self) -> bool:
        return self.method == DELETE

    @property
    def is_xhr(self) -> bool:
        if "HTTP_X_REQUESTED_WITH" in self.env:
            return self.env["HTTP_X_REQUESTED_WITH"] == "XMLHttpRequest"
        return False

    @property
    def url(self) -> str:
        """Returns the current URL."""
        url_ = f"{self.host_with_port}{self.path}"
        query_string = self.query_string
        if query_string:
            url_ = f"{url_}?{query_string}"
        return url_

    @property
    def query_string(self) -> str:
        return self.env.get("QUERY_STRING", "")

    @property
    def host_with_port(self) -> str:
        """Returns a host:port string for this request, such as “example.com” or
        “example.com:8080”.
        Port is only included if it is not a default port (80 or 443)
        """
        return f"{self.host}{self.port_string}"

    @property
    def port_string(self) -> str:
        return "" if self.port_is_default else f":{self.port}"

    @property
    def port_is_default(self) -> bool:
        return self.port == self.default_port

    @property
    def default_port(self) -> int:
        return DEFAULT_HTTPS_PORT if self.protocol == "https" else DEFAULT_HTTP_PORT

    @property
    def is_ssl(self) -> bool:
        return self.protocol == "https"

    @property
    def remote_ip(self) -> str:
        """Passed-forward IP address of the client or IP address of the
        closest proxy to the WSGI server.
        """
        if self._remote_ip is None:
            addr = None
            if "HTTP_X_FORWARDED_FOR" in self.env:
                addr = self.env["HTTP_X_FORWARDED_FOR"]
            if "HTTP_X_REAL_IP" in self.env:
                addr = self.env["HTTP_X_REAL_IP"]
            elif "REMOTE_ADDR" in self.env:
                addr = self.env["REMOTE_ADDR"]
            addr = addr or "127.0.0.1"
            self._remote_ip = addr
        return self._remote_ip

    @property
    def content_length(self) -> int:
        """The content_length value as an integer."""
        if self._content_length is None:
            length = self.env.get("CONTENT_LENGTH", "0")
            self._content_length = self._validate_content_length(length)
        return self._content_length

    @property
    def headers(self) -> HeadersDict:
        if self._headers is None:
            headers = HeadersDict()
            for name, value in self.env.items():
                name = name.upper()
                if name.startswith(("HTTP_", "HTTP-")):
                    headers[name[5:]] = value
                headers[name] = value
            self._headers = headers
        return self._headers

    @property
    def accepts(self) -> List[str]:
        if self._accepts is None:
            value = self.env.get("HTTP_ACCEPT", "")
            _accepts = [mime for mime, q in parse_accept_header(value)]
            if not _accepts and self.content_type:
                _accepts = [self.content_type]
            self._accepts = _accepts

        return self._accepts

    @property
    def format(self) -> str:
        if self._format is None:
            for mime in self.accepts:
                if mime == MIME_ALL:
                    break
                ext = mimetypes.guess_extension(mime)
                if ext:
                    self._format = ext[1:]
                    break

            self._format = self._format or DEFAULT_FORMAT
        return self._format

    @property
    def if_none_match(self) -> List[str]:
        """Value of the If-None-Match header, as a parsed list of strings,
        or an empty list if the header is missing or its value is blank.
        """
        if self._if_none_match is None:
            header = self.env.get("HTTP_IF_NONE_MATCH", "")
            self._if_none_match = parse_comma_separated(header)
        return self._if_none_match

    @property
    def if_modified_since(self) -> Union[datetime, str]:
        if self._if_modified_since is None:
            header = self.env.get("HTTP_IF_MODIFIED_SINCE", "")
            self._if_modified_since = parse_http_date(header) or ""
        return self._if_modified_since

    @property
    def languages(self) -> List[str]:
        if self._languages is None:
            value = self.env.get("HTTP_ACCEPT_LANGUAGES", "")
            self._languages = [
                lang.lower().replace("_", "-")
                for lang, q in parse_accept_header(value)
            ]

        return self._languages

    @property
    def body(self) -> Any:
        return self.env.get("wsgi.input", BytesIO())

    @property
    def query(self) -> MultiDict:
        if self._query is None:
            query_string = self.query_string
            self._query = parse_query_string(query_string, self.max_query_size)
        return self._query

    @property
    def form(self) -> MultiDict:
        if self._form is None:
            # GET and HEAD can't have form data.
            if self.method in (GET, HEAD):
                self._form = MultiDict()
            else:
                self._form = parse_form_data(
                    self.body,
                    self.content_type,
                    self.content_length,
                    self.encoding,
                    self.max_content_length,
                )
        return self._form

    @property
    def cookies(self) -> Dict[str, Any]:
        if self._cookies is None:
            self._cookies = parse_cookies(self.env.get("HTTP_COOKIE"))
        return self._cookies

    @property
    def session(self) -> Dict[str, Any]:
        return self._session

    @property
    def flashes(self) -> Dict[str, Any]:
        return self._session.get(FLASHES_SESSION_KEY, {})

    # Private

    def _validate_content_length(self, length: Union[int, str]) -> int:
        try:
            ilength = int(length)
        except ValueError:
            raise errors.InvalidHeader("The Content-Length header must be a number.")
        if ilength < 0:
            raise errors.InvalidHeader(
                "The value of the Content-Length header must be a positive number."
            )
        return ilength


def make_test_environ(path: str = None, **kwargs: Dict[str, Any]) -> Dict[str, str]:
    from wsgiref.util import setup_testing_defaults

    environ = {"REMOTE_ADDR": "127.0.0.1"}
    setup_testing_defaults(environ)

    if path:
        if "?" in path:
            path, query = path.rsplit("?", 1)
            environ["QUERY_STRING"] = query
        environ["PATH_INFO"] = tunnel_encode(path.strip())

    environ.update(**{key: str(value) for key, value in kwargs.items()})
    return environ
