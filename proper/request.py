"""
Request class.
"""
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


__all__ = ("Request", "make_test_environ")

DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443


class Request:
    """An HTTP request.

    Arguments are:

        encoding (str):
            Default encoding.

        config (dict):
            Extra options

        **environ (dict):
            A WSGI environment dict passed in from the server (See also PEP-3333).

    Attributes:

        environ (dict):
            The WSGI environment dict passed in from the server.

        scheme (str):
            The request scheme as an string (either "http" or "https").

        host (str):
            The requested host.

        host_with_port (str):
            A host:port string for this request. The port is not included
            if its the default for the scheme.

        method (str):
            The uppercased request method, example: "GET".

        path (str):
            Requested path without the leading or trailing slash.

        query (MultiDict):
            Parsed args from the URL.

        form (MultiDict):
            A :class:`MultiDict` object containing the parsed body data, like the
            one sent by a HTML form with a POST, **including** the files.

        remote_addr (str):
            IP address of the closest client or proxy to the WSGI server.

            If your application is behind one or more reverse proxies,
            and it doesn't pass forward the IP address of the client,
            you can use the `access_route` attribute to retrieve the real
            IP address of the client.

        root_path (str):
            The root path of the script (SCRIPT_NAME).
            Note: The router does **NOT** uses this value for `url_for()`, but the
            one from `app.config.root_path`.
            A :class:`MultiDict` object containing the query string data.

        cookies (dict):
            All cookies transmitted with the request.

        xhr (bool):
            True if current request is an XHR request.

        secure (bool):
            Whether the current request was made via a SSL connection.

        content_type (str):
            The MIME content type of the incoming request.

        content_length (int):
            The length in bytes, as an integer, of the content sent by the client.

        stream (stream):
            Returns the contents of the incoming HTTP entity body.

        flashes (list):
            The flashed messages stored in the session cookie.
            By reading this value it will be stored in the request but
            deleted form the session.

        if_none_match (list):
            Value of the If-None-Match header, as a parsed list of strings,
            or an empty list if the header is missing or its value is blank.

        if_modified_since (datetime):
            Value of the If-Modified-Since header, or an empty string if the header
            is missing or the date cannot be parsed.

    """

    matched_route = None
    matched_params = None
    user = None
    csrf_token = None
    _session = None

    def __init__(
        self,
        *,
        encoding="utf8",
        config=None,
        **environ,
    ):
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

        self._content_length = None
        self._cookies = None
        self._form = None
        self._headers = None
        self._query = None
        self._remote_addr = None
        self._session = {}
        self._if_none_match = None
        self._if_modified_since = None

    def __repr__(self):
        return f"<Request {self.method} “{self.path}”>"

    def _parse_host(self, host):
        _defport = DEFAULT_HTTPS_PORT if self.scheme == "https" else DEFAULT_HTTP_PORT
        if not host:
            return "", _defport

        port = None

        if "]:" in host:
            host, port = host.split("]:", 1)
            host = host[1:]
        elif host[0] == "[":
            host = host[1:-1]
        elif ":" in host:
            host, port = host.rsplit(":", 1)

        port = int(port) if port and port.isdecimal() else _defport
        return host, port

    @property
    def port_is_default(self):
        return (self.port == DEFAULT_HTTPS_PORT and self.scheme == "https") or (
            self.port == DEFAULT_HTTP_PORT
        )

    @property
    def host_with_port(self):
        """Returns a host:port string for this request, such as “example.com” or
        “example.com:8080”.
        Port is only included if it is not a default port (80 or 443)
        """
        if self.port_is_default:
            return self.host
        return f"{self.host}:{self.port}"

    @property
    def url(self):
        """Returns the current URL."""
        url_ = f"{self.host_with_port}{self.path}"
        query_string = self.environ.get("QUERY_STRING", "")
        if query_string:
            url_ = f"{url_}?{query_string}"
        return url_

    @property
    def content_length(self):
        """The content_length value as an integer."""
        if self._content_length is None:
            length = self.environ.get("CONTENT_LENGTH", "0")
            self._content_length = self._validate_content_length(length)
        return self._content_length

    def _validate_content_length(self, length):
        try:
            length = int(length)
        except ValueError:
            raise errors.InvalidHeader("The Content-Length header must be a number.")
        if length < 0:
            raise errors.InvalidHeader(
                "The value of the Content-Length header must be a positive number."
            )
        return length

    @property
    def cookies(self):
        if self._cookies is None:
            self._cookies = parse_cookies(self.environ.get("HTTP_COOKIE"))
        return self._cookies

    @property
    def flashes(self):
        return self._session.get(FLASHES_SESSION_KEY, [])

    @property
    def form(self):
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
    def headers(self):
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
    def is_get(self):
        return self.method == GET

    @property
    def is_head(self):
        return self.real_method == HEAD

    @property
    def is_post(self):
        return self.method == POST

    @property
    def is_put(self):
        return self.method == PUT

    @property
    def is_patch(self):
        return self.method == PATCH

    @property
    def is_delete(self):
        return self.method == DELETE

    @property
    def query(self):
        if self._query is None:
            query_string = self.environ.get("QUERY_STRING", "")
            self._query = parse_query_string(query_string, self.config)
        return self._query

    @property
    def remote_addr(self):
        """Passed-forward IP address of the client or IP address of the
        closest proxy to the WSGI server.
        """
        if self._remote_addr is None:
            addr = None
            if "HTTP_X_FORWARDED_FOR" in self.environ:
                addr = self.environ["HTTP_X_FORWARDED_FOR   "]
            if "HTTP_X_REAL_IP" in self.environ:
                addr = self.environ["HTTP_X_REAL_IP"]
            elif "REMOTE_ADDR" in self.environ:
                addr = self.environ["REMOTE_ADDR"]
            addr = addr or "127.0.0.1"
            self._remote_addr = addr
        return self._remote_addr

    @property
    def root_path(self):
        return self.environ.get("SCRIPT_NAME")

    @property
    def secure(self):
        return self.scheme == "https"

    @property
    def session(self):
        return self._session

    @property
    def stream(self):
        return self.environ["wsgi.input"]

    @property
    def xhr(self):
        if "HTTP_X_REQUESTED_WITH" in self.environ:
            return self.environ["HTTP_X_REQUESTED_WITH"] == "XMLHttpRequest"
        return False

    def must_check_csrf(self):
        """Return wether the CSRF token in this request must be checked
        for validity."""
        return self.method in (POST, PUT, DELETE, PATCH)

    @property
    def if_none_match(self):
        """Value of the If-None-Match header, as a parsed list of strings,
        or an empty list if the header is missing or its value is blank.
        """
        if self._if_none_match is None:
            header = self.environ.get("HTTP_IF_NONE_MATCH", "")
            self._if_none_match = parse_comma_separated(header)
        return self._if_none_match

    @property
    def if_modified_since(self):
        if self._if_modified_since is None:
            header = self.environ.get("HTTP_IF_MODIFIED_SINCE", "")
            self._if_modified_since = parse_http_date(header)
        return self._if_modified_since


def make_test_environ(path=None, **kwargs):
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
