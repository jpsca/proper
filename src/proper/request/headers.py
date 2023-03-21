import mimetypes
import re
import typing as t
from datetime import datetime
from functools import cached_property
from http.cookies import Morsel, SimpleCookie

from proper.constants import DELETE, GET, HEAD, PATCH, POST, PUT
from proper.helpers import parse_http_date, tunnel_decode
from proper.errors import InvalidHeader

from .forwarded import Forwarded, parse_forwarded


DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443

MIME_ALL = "*/*"


class RequestHeadersMixin:
    """Mixin with the methods related to the request headers.
    """

    DEFAULT_FORMAT = "html"

    env: dict[str, t.Any]

    def __init__(self):
        host, port = parse_host(self.env.get("HTTP_HOST"))
        self.host = host
        self.port = port or self.default_port

        self.protocol = self.env.get(
            "HTTP_FORWARDED_PROTO",
            self.env.get("wsgi.url_protocol")
        )

        self.method = self.env.get("REQUEST_METHOD", GET).upper()
        self.request_method = self.method

        # PATH_INFO is always "bytes tunneled as latin-1" and must be decoded back.
        path_info = self.env.get("PATH_INFO", "").strip("/")
        self.path = "/" + tunnel_decode(path_info)

        self.content_type = self.env.get("CONTENT_TYPE", "")

        try:
            self.content_length = int(self.env.get("CONTENT_LENGTH", "0"))
        except ValueError:
            raise InvalidHeader("The Content-Length header must be a number.")
        if self.content_length < 0:
            raise InvalidHeader(
                "The value of the Content-Length header must be a positive number."
            )

    @cached_property
    def accept(self) -> list[str]:
        """Parse the `accept` header.

        Indicates which content types, expressed as MIME types,
        the client is able to understand. Your app should select one of the proposals
        and informs the client of that choice with the `Content-Type`
        response header.

        """
        return parse_accept(self.env.get("HTTP_ACCEPT"))

    @cached_property
    def accept_encoding(self) -> list[str]:
        """Parse the `accept-encoding` header.

        Indicates the content encoding (usually a compression algorithm) that
        the client can understand. Your app should select one of the proposals
        and informs the client of that choice with the `Content-Encoding`
        response header.

        """
        return parse_accept(self.env.get("HTTP_ACCEPT_ENCODING"))

    @cached_property
    def accept_language(self) -> list[str]:
        """Parse the `accept-language` header.

        Indicates the natural language and locale that the client prefers.
        Your app should select one of the proposals and informs the client
        of that choice with the `Content-Encoding` response header.

        This header serves as a hint when the server cannot determine the target
        content language otherwise (for example, use a specific URL that
        depends on an explicit user decision).

        The server should never override an explicit user language choice.
        The content of `Accept-Language` is often out of a user's control
        (when traveling, for instance) and a user may also want to visit a page
        in a language different from the browser language.

        """
        return parse_accept(self.env.get("HTTP_ACCEPT_LANGUAGE"))

    @cached_property
    def cookie(self) -> dict[str, Morsel]:
        """Parse the `cookie` header.
        """
        return parse_cookie(self.env.get("HTTP_COOKIE"))

    @property
    def cookies(self) -> dict:
        """Parse the `cookie` header.
        """
        return self.cookies

    @cached_property
    def date(self) -> datetime | None:
        """Parse the `date` header.

        The date and time at which the message originated.
        """
        val = self.env.get("HTTP_DATE")
        return parse_http_date(val)

    @property
    def default_port(self) -> int:
        """Returns the default port for the protocol."""
        return DEFAULT_HTTPS_PORT if self.protocol == "https" else DEFAULT_HTTP_PORT

    @cached_property
    def format(self) -> str:
        """Parse the `accept` header and try to return the default extension
        (for example: html, json, etc.) for the first mimetype of the list
        that has one.
        """
        val = None
        for mime in self.accept:
            if mime == MIME_ALL:
                break
            ext = mimetypes.guess_extension(mime)
            if ext:
                val = ext[1:]
                break
        return val or self.DEFAULT_FORMAT

    @cached_property
    def forwarded(self) -> list[dict]:
        """Parse the `forwarded` header.

        The `Forwarded` header is a comma-separated list of forwarding
        information from the client to the server on its way through proxies.
        """
        return parse_forwarded(self.env.get("HTTP_FORWARDED"))

    @property
    def host_with_port(self) -> str:
        """Returns a host:port string for this request, such as “example.com” or
        “example.com:8080”.
        Port is only included if it is not a default port (80 or 443)
        """
        return f"{self.host}{self.port_string}"

    @property
    def is_delete(self) -> bool:
        """True if the method is DELETE."""
        return self.method == DELETE

    @property
    def is_get(self) -> bool:
        """True if the method is GET."""
        return self.method == GET

    @property
    def is_head(self) -> bool:
        """True if the method is HEAD."""
        return self.request_method == HEAD

    @property
    def is_patch(self) -> bool:
        """True if the method is PATCH."""
        return self.method == PATCH

    @property
    def is_post(self) -> bool:
        """True if the method is POST."""
        return self.method == POST

    @property
    def is_put(self) -> bool:
        """True if the method is PUT."""
        return self.method == PUT

    @property
    def is_ssl(self) -> bool:
        """True if the protocol is HTTPS."""
        return self.protocol == "https"

    @property
    def is_xhr(self) -> bool:
        """True if the request was done by JavaScript."""
        return self.env.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"

    @property
    def port_is_default(self) -> bool:
        """True if the port is the default port for the protocol."""
        return self.port == self.default_port

    @property
    def port_string(self) -> str:
        """Returns the port as a string, or an empty string if the port is the
        default port for the protocol."""
        return "" if self.port_is_default else f":{self.port}"

    @property
    def remote_ip(self) -> str:
        """IP address of the closest client or proxy to the WSGI server.

        This will use the `Forwarded` header to try to found the real
        IP address of the client if your application is behind one or
        more reverse proxies,
        """
        for fw in self.forwarded:
            if "for" in fw:
                return fw["for"]

        ff = self.env.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if ff:
            return ff[0]

        realip = self.env.get("HTTP_X_REAL_IP")
        if realip:
            return realip

        return self.env.get("REMOTE_ADDR", "")

    @cached_property
    def request_id(self) -> str | None:
        """Parse the `x-request-id` header.

        This header is used to uniquely identify a request.
        """
        val = self.env.get("HTTP_X_REQUEST_ID")
        return parse_request_id(val)

    def get_header(self, name: str, default: t.Any = None) -> t.Any:
        name = name.strip().lower().replace("-", "_").removeprefix("http_")
        if hasattr(self, name):
            return getattr(self, name, default)

        name = f"HTTP_{name}"
        value = self.env.get(name)
        return default if value is None else value


## Parsers -----


def parse_accept(value: str | None) -> list[str]:
    if value is None:
        return []

    values = parse_multivalue(value)
    # Sorted by weight, in descending order
    ranking = sorted(
        [
            (
                label.lower().replace("_", "-"),
                float(params.get("q", 1.0))
            )
            for label, params in values
        ],
        key=lambda tup: tup[1],
        reverse=True
    )
    # Return only the labels
    return [label for label, _ in ranking]


RX_COMMA = re.compile(r",\s*")


def parse_comma_separated(value: str | None) -> list[str]:
    if value is None:
        return []

    return RX_COMMA.split(value.strip(" ,"))


def parse_cookie(value: str | None) -> dict[str, Morsel]:
    if value is None:
        return {}

    cookie = SimpleCookie()
    cookie.load(value)
    return cookie


def parse_host(value: str | None) -> tuple[str, int]:
    value = value or ""
    sport = ""

    if "]:" in value:
        host, sport = value.split("]:", 1)
        host = value[1:]
    elif value[0] == "[":
        host = value[1:-1]
    elif ":" in value:
        host, sport = value.rsplit(":", 1)
    else:
        host = ""

    port = int(sport) if sport and sport.isdecimal() else 0
    return host, port


#: Header tokenizer used by parse_multivalue()
RX_SPLIT = re.compile('(?:(?:"((?:[^"\\\\]|\\\\.)*)")|([^;,=]+))([;,=]?)').findall


def parse_multivalue(header: str) -> list[tuple[str, dict]]:
    """Parses a typical multi-valued and parametrised HTTP header
    (e.g. Accept headers) and returns a list of values and parameters.
    For non-standard or broken input, this implementation may return partial results.

    Arguments:
        header: A header string (e.g. `text/html,text/plain;q=0.9,*/*;q=0.8`)

    Return:
        List of (value, params) tuples. The second element is a
        (possibly empty) dict.
    """
    values = []
    if '"' not in header:  # INFO: Fast path without regexp (~2x faster)
        for value in header.split(","):
            parts = value.split(";")
            values.append((parts[0].strip(), {}))
            for attr in parts[1:]:
                name, value = attr.split("=", 1)
                values[-1][1][name.strip()] = value.strip()
    else:
        lop, key, attrs = ",", None, {}
        for quoted, plain, tok in RX_SPLIT(header):
            value = plain.strip() if plain else quoted.replace('\\"', '"')
            if lop == ",":
                attrs = {}
                values.append((value, attrs))
            elif lop == ";":
                if tok == "=":
                    key = value
                else:
                    attrs[value] = ""
            elif lop == "=" and key:
                attrs[key] = value
                key = None
            lop = tok
    return values


REQUEST_ID_MAX_LENGTH = 200
RX_NON_ASCII = re.compile(r"[^\x00-\x7f-]")


def parse_request_id(val: str | None) -> str | None:
    if val is None:
        return None
    val = str(val)[:REQUEST_ID_MAX_LENGTH]
    return RX_NON_ASCII.sub("", val)
