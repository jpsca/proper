"""
Request class.

"""
from . import errors
from .constants import GET, HEAD, POST, PUT, PATCH, DELETE, FLASHES_SESSION_KEY
from .parsers import parse_host, parse_query_string, parse_cookies, parse_form_data
from .helpers import (
    tunnel_encode,
    tunnel_decode,
    MultiDict,
    HeadersDict,
)


__all__ = ("Request", "make_test_environ")


class Request:
    """An HTTP request.

    Arguments are:

        environ (dict):
            A WSGI environment dict passed in from the server (See also PEP-3333).
            If none is passed, a default one will be used instead.

        start_response (function):
            A WSGI `start_response` function from the server (See also PEP-3333).

        encoding (str):
            "utf8" by default

        method (str)
        host (str)
        path (str)
        **kwargs (dict):
            Update the values of the environment (used for testing).

    Attributes:

        environ (dict):
            The WSGI environment dict passed in from the server.

        method (str):
            The uppercased request method, example: "GET".

        path (str):
            Requested path without the leading or trailing slash.


    Lazy-loaded attributes:

    The information in these attributes is not populated until they are readed for the
    first time.

        host (str):
            The requested host.

        remote_addr (str):
            IP address of the closest client or proxy to the WSGI server.

            If your application is behind one or more reverse proxies,
            and it doesn"t pass forward the IP address of the client,
            you can use the `access_route` attribute to retrieve the real
            IP address of the client.

        root_path (str):
            The root path of the script (SCRIPT_NAME).
            Note: The router does **NOT** uses this value for `url_for()`, but the
            one from `app.config.root_path`.

        query (MultiDict):
            A :class:`MultiDict` object containing the query string data.

        form (MultiDict):
            A :class:`MultiDict` object containing the parsed body data, like the
            one sent by a HTML form with a POST, **including** the files.

        cookies (dict):
            All cookies transmitted with the request.

        xhr (bool)
            True if current request is an XHR request.

        scheme (str):
            The request scheme as an string (either "http" or "https").

        secure (bool)
            Whether the current request was made via a SSL connection.

        content_type (str):
            The MIME content type of the incoming request.

        content_length (int):
            The length in bytes, as an integer, of the content sent by the client.

        stream (stream)
            Returns the contents of the incoming HTTP entity body.

        flashes (list):
            The flashed messages stored in the session cookie.
            By reading this value it will be stored in the request but
            deleted form the session.

    """

    matched_route = None
    matched_params = None
    user = None
    csrf_token = None
    _session = None

    def __init__(
        self,
        environ=None,
        start_response=None,
        *,
        encoding="utf8",
        config=None,
        **kwargs,
    ):
        environ = self._normalize_environment(environ, kwargs)
        self.environ = environ
        self.start_response = start_response
        self.encoding = encoding
        self.config = config or {}

        self.method = environ["REQUEST_METHOD"].upper()
        self.real_method = self.method
        # PATH_INFO is always "bytes tunneled as latin-1" and must be decoded back.
        # Read the docstring on `support/encoding.py` for more details.
        self.path = "/" + tunnel_decode(environ["PATH_INFO"].strip("/"))
        self.content_type = self.environ["CONTENT_TYPE"]

        self._content_length = None
        self._cookies = None
        self._form = None
        self._headers = None
        self._host = None
        self._query = None
        self._remote_addr = None
        self._session = {}

    def _normalize_environment(self, environ, kwargs):
        environ = environ or make_test_environ(**kwargs)
        environ.setdefault("HTTP_HOST", "")
        environ.setdefault("QUERY_STRING", "")
        environ.setdefault("CONTENT_LENGTH", "0")
        environ.setdefault("CONTENT_TYPE", "")
        return environ

    def __repr__(self):
        return f"<Request {self.method} “{self.path}”>"

    @property
    def content_length(self):
        """The content_length value as an integer.
        """
        if self._content_length is None:
            length = self.environ["CONTENT_LENGTH"]
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
    def host(self):
        if self._host is None:
            self._host = parse_host(self.environ["HTTP_HOST"])
        return self._host

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
            query_string = self.environ.get("QUERY_STRING")
            self._query = parse_query_string(query_string, self.config)
        return self._query

    @property
    def remote_addr(self):
        """Passed-forward IP address of the client or IP address of the
        closest proxy to the WSGI server.
        """
        if self._remote_addr is None:
            addr = "127.0.0.1"
            if "HTTP_X_REAL_IP" in self.environ:
                addr = self.environ["HTTP_X_REAL_IP"]
            elif "REMOTE_ADDR" in self.environ:
                addr = self.environ["REMOTE_ADDR"]
            self._remote_addr = addr
        return self._remote_addr

    @property
    def root_path(self):
        return self.environ.get("SCRIPT_NAME")

    @property
    def scheme(self):
        return self.environ.get("HTTP_X_FORWARDED_PROTO") \
            or self.environ.get("wsgi.url_scheme")

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


def make_test_environ(method=None, host=None, path=None, **kwargs):
    from wsgiref.util import setup_testing_defaults

    environ = {"REMOTE_ADDR": "127.0.0.1"}
    setup_testing_defaults(environ)

    if method:
        environ["REQUEST_METHOD"] = method.upper()
    if host:
        environ["HTTP_HOST"] = host
    if path:
        if "?" in path:
            path, query = path.rsplit("?", 1)
            environ["QUERY_STRING"] = query
        environ["PATH_INFO"] = tunnel_encode(path.strip())

    environ.update(**{key: str(value) for key, value in kwargs.items()})
    return environ
