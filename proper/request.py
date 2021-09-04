"""
Request class.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from . import errors
from .constants import DELETE, FLASHES_SESSION_KEY, GET, HEAD, PATCH, POST, PUT
from .helpers import HeadersDict, MultiDict, tunnel_decode, tunnel_encode
from .parsers import (
    parse_comma_separated,
    parse_cookies,
    parse_form_data,
    parse_http_date,
    parse_query_string,
)
from .router import Route


__all__ = ("Request", "make_test_environ")

DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443


class Request:
    """An HTTP request.

    Arguments are:

    encoding:
        Default encoding.

    config:
        Extra options

    **environ:
        A WSGI environment dict passed in from the server (See also PEP-3333).


    Attributes:

    environ:
        The WSGI environment dict passed in from the server.

    scheme:
        The request scheme as an string (either "http" or "https").

    host:
        The requested host.

    host_with_port:
        A host:port string for this request. The port is not included
        if its the default for the scheme.

    method:
        The uppercased request method, example: "GET".

    path:
        Requested path without the leading or trailing slash.

    query:
        Parsed args from the URL.

    form:
        A :class:`MultiDict` object containing the parsed body data, like the
        one sent by a HTML form with a POST, **including** the files.

    remote_addr:
        IP address of the closest client or proxy to the WSGI server.

        If your application is behind one or more reverse proxies,
        and it doesn't pass forward the IP address of the client,
        you can use the `access_route` attribute to retrieve the real
        IP address of the client.

    root_path:
        The root path of the script (SCRIPT_NAME).
        Note: The router does **NOT** uses this value for `url_for()`, but the
        one from `app.config.root_path`.
        A :class:`MultiDict` object containing the query string data.

    cookies:
        All cookies transmitted with the request.

    xhr:
        True if current request is an XHR request.

    secure:
        Whether the current request was made via a SSL connection.

    content_type:
        The MIME content type of the incoming request.

    content_length:
        The length in bytes, as an integer, of the content sent by the client.

    stream:
        Returns the contents of the incoming HTTP entity body.

    flashes:
        The flashed messages stored in the session cookie.
        By reading this value it will be stored in the request but
        deleted form the session.

    if_none_match:
        Value of the If-None-Match header, as a parsed list of strings,
        or an empty list if the header is missing or its value is blank.

    if_modified_since:
        Value of the If-Modified-Since header, or an empty string if the header
        is missing or the date cannot be parsed.

    """

    encoding: str
    config: Dict[str, Any]
    environ: Dict[str, Any]
    method: str
    real_method: str
    path: str
    content_type: str
    scheme: str
    host: str
    port: int

    matched_route: Optional[Route]
    matched_params: Optional[Dict[str, Any]]
    user: Optional[Any]
    csrf_token: Optional[str]

    _session: Dict[str, Any]

    def __init__(
        self,
        *,
        encoding: str = "utf8",
        config: Optional[Dict[str, Any]] = None,
        **environ,
    ) -> None:
        self.encoding = encoding
        self.config = config or {}
        environ = environ or make_test_environ()
        self.environ = environ

        self.method = environ.get("REQUEST_METHOD", "GET").upper()
        self.real_method = self.method

        # PATH_INFO is always "bytes tunneled as latin-1" and must be decoded back.
        # Read the docstring on `support/encoding.py` for more details.
        self.path = "/" + tunnel_decode(environ.get("PATH_INFO", "").strip("/"))

        self.content_type = self.environ.get("CONTENT_TYPE", "")

        self.scheme = self.environ.get("HTTP_X_FORWARDED_PROTO") or self.environ.get(
            "wsgi.url_scheme"
        )
        self.host, self.port = self._parse_host(self.environ.get("HTTP_HOST"))

        self.matched_route = None
        self.matched_params = None
        self.user = None
        self.csrf_token = None
        self._session = {}

        self._content_length = None
        self._cookies = None
        self._form = None
        self._headers = None
        self._query = None
        self._remote_addr = None
        self._if_none_match = None
        self._if_modified_since = None

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    def _parse_host(self, host: str) -> Tuple[str, int]:
        _defport = DEFAULT_HTTPS_PORT if self.scheme == "https" else DEFAULT_HTTP_PORT
        if not host:
            return "", _defport

        sport: str = ""

        if "]:" in host:
            host, sport = host.split("]:", 1)
            host = host[1:]
        elif host[0] == "[":
            host = host[1:-1]
        elif ":" in host:
            host, sport = host.rsplit(":", 1)

        port = int(sport) if sport and sport.isdecimal() else _defport
        return host, port

    @property
    def port_is_default(self) -> bool:
        return (self.port == DEFAULT_HTTPS_PORT and self.scheme == "https") or (
            self.port == DEFAULT_HTTP_PORT
        )

    @property
    def host_with_port(self) -> str:
        """Returns a host:port string for this request, such as “example.com” or
        “example.com:8080”.
        Port is only included if it is not a default port (80 or 443)
        """
        if self.port_is_default:
            return self.host
        return f"{self.host}:{self.port}"

    @property
    def url(self) -> str:
        """Returns the current URL."""
        url_ = f"{self.host_with_port}{self.path}"
        query_string = self.environ.get("QUERY_STRING", "")
        if query_string:
            url_ = f"{url_}?{query_string}"
        return url_

    @property
    def content_length(self) -> int:
        """The content_length value as an integer."""
        if self._content_length is None:
            length = self.environ.get("CONTENT_LENGTH", "0")
            self._content_length = self._validate_content_length(length)
        return self._content_length

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

    @property
    def cookies(self) -> Dict[str, Any]:
        if self._cookies is None:
            self._cookies = parse_cookies(self.environ.get("HTTP_COOKIE"))
        return self._cookies

    @property
    def flashes(self) -> List[Dict[str, Any]]:
        return self._session.get(FLASHES_SESSION_KEY, [])

    @property
    def form(self) -> MultiDict:
        if self._form is None:
            # GET and HEAD can't have form data.
            if self.method in (GET, HEAD):
                self._form = MultiDict()
            else:
                self._form = parse_form_data(
                    self.stream,
                    self.content_type,
                    self.content_length,
                    self.encoding,
                    self.config,
                )
        return self._form

    @property
    def headers(self) -> HeadersDict:
        if self._headers is None:
            headers = HeadersDict()
            for name, value in self.environ.items():
                name = name.upper()
                if name.startswith(("HTTP_", "HTTP-")):
                    headers[name[5:]] = value
                headers[name] = value
            self._headers = headers
        return self._headers

    @property
    def is_get(self) -> bool:
        return self.method == GET

    @property
    def is_head(self) -> bool:
        return self.real_method == HEAD

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
    def query(self) -> MultiDict:
        if self._query is None:
            query_string = self.environ.get("QUERY_STRING", "")
            self._query = parse_query_string(query_string, self.config)
        return self._query

    @property
    def remote_addr(self) -> str:
        """Passed-forward IP address of the client or IP address of the
        closest proxy to the WSGI server.
        """
        if self._remote_addr is None:
            addr = None
            if "HTTP_X_FORWARDED_FOR" in self.environ:
                addr = self.environ["HTTP_X_FORWARDED_FOR"]
            if "HTTP_X_REAL_IP" in self.environ:
                addr = self.environ["HTTP_X_REAL_IP"]
            elif "REMOTE_ADDR" in self.environ:
                addr = self.environ["REMOTE_ADDR"]
            addr = addr or "127.0.0.1"
            self._remote_addr = addr
        return self._remote_addr

    @property
    def root_path(self) -> str:
        return self.environ.get("SCRIPT_NAME")

    @property
    def secure(self) -> bool:
        return self.scheme == "https"

    @property
    def session(self) -> Dict[str, Any]:
        return self._session

    @property
    def stream(self) -> Any:
        return self.environ["wsgi.input"]

    @property
    def xhr(self) -> bool:
        if "HTTP_X_REQUESTED_WITH" in self.environ:
            return self.environ["HTTP_X_REQUESTED_WITH"] == "XMLHttpRequest"
        return False

    def must_check_csrf(self) -> bool:
        """Return wether the CSRF token in this request must be checked
        for validity."""
        return self.method in (POST, PUT, DELETE, PATCH)

    @property
    def if_none_match(self) -> List[str]:
        """Value of the If-None-Match header, as a parsed list of strings,
        or an empty list if the header is missing or its value is blank.
        """
        if self._if_none_match is None:
            header = self.environ.get("HTTP_IF_NONE_MATCH", "")
            self._if_none_match = parse_comma_separated(header)
        return self._if_none_match

    @property
    def if_modified_since(self) -> Union[datetime, str]:
        if self._if_modified_since is None:
            header = self.environ.get("HTTP_IF_MODIFIED_SINCE", "")
            self._if_modified_since = parse_http_date(header) or ""
        return self._if_modified_since


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
