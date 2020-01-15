"""
## proper.request

Request class.

"""
from wsgiref.util import setup_testing_defaults

from . import errors
from .constants import GET, HEAD, POST, PUT, PATCH, DELETE, FLASHES_SESSION_KEY
from .parsers import parse_host, parse_query_string, parse_cookies, parse_form_data
from .support import (
    cached_property,
    tunnel_encode,
    tunnel_decode,
    MultiDict,
    HeadersDict,
)


__all__ = ("Request", "make_test_environ")


class Request(object):
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
    template = None
    __session = None
    __original_session = None

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

        self.__session = {}
        self.__original_session = {}

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

    @cached_property
    def host(self):
        return parse_host(self.environ["HTTP_HOST"])

    @cached_property
    def content_type(self):
        return self.environ["CONTENT_TYPE"]

    @cached_property
    def content_length(self):
        """The content_length value as an integer.
        """
        try:
            length = int(self.environ["CONTENT_LENGTH"])
        except ValueError:
            raise errors.InvalidHeader("The Content-Length header must be a number.")
        if length < 0:
            raise errors.InvalidHeader(
                "The value of the Content-Length header must be a positive number."
            )
        return length

    @cached_property
    def scheme(self):
        return self.environ.get("HTTP_X_FORWARDED_PROTO") or self.environ.get(
            "wsgi.url_scheme"
        )

    @cached_property
    def secure(self):
        return self.scheme == "https"

    @cached_property
    def remote_addr(self):
        """Passed-forward IP address of the client or IP address of the
        closest proxy to the WSGI server.
        """
        addr = None
        if "HTTP_X_REAL_IP" in self.environ:
            addr = self.environ["HTTP_X_REAL_IP"]
        elif "REMOTE_ADDR" in self.environ:
            addr = self.environ["REMOTE_ADDR"]
        return addr

    @cached_property
    def root_path(self):
        return self.environ.get("SCRIPT_NAME")

    @cached_property
    def xhr(self):
        if "HTTP_X_REQUESTED_WITH" in self.environ:
            return self.environ["HTTP_X_REQUESTED_WITH"] == "XMLHttpRequest"
        return False

    @cached_property
    def headers(self):
        headers = HeadersDict()

        for name, value in self.environ.items():
            name = name.upper()
            if name.startswith("HTTP_"):
                headers[name[5:]] = value

        headers["CONTENT_TYPE"] = self.environ.get("CONTENT_TYPE") or None
        headers["CONTENT_LENGTH"] = self.environ.get("CONTENT_LENGTH") or None
        return headers

    @cached_property
    def query(self):
        query_string = self.environ.get("QUERY_STRING")
        try:
            return parse_query_string(query_string, self.config)
        except ValueError:
            raise errors.BadRequest()

    @cached_property
    def form(self):
        # GET and HEAD can't have form data.
        if self.method in (GET, HEAD):
            return MultiDict()

        try:
            return parse_form_data(
                self.stream,
                self.content_type,
                self.content_length,
                self.encoding,
                self.config,
            )
        except ValueError:
            raise errors.BadRequest()

    @cached_property
    def cookies(self):
        try:
            return parse_cookies(self.environ.get("HTTP_COOKIE"))
        except ValueError:
            return {}

    @cached_property
    def stream(self):
        return self.environ["wsgi.input"]

    def must_check_csrf(self):
        """Return wether the CSRF token in this request must be checked
        for validity."""
        return self.method in (POST, PUT, DELETE, PATCH)

    @cached_property
    def flashes(self):
        return self.session.pop(FLASHES_SESSION_KEY, [])

    @property
    def session(self):
        return self.__session

    @property
    def original_session(self):
        return self.__original_session


def make_test_environ(method=None, host=None, path=None, **kwargs):
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
