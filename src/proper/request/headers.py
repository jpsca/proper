import mimetypes
import re
import typing as t
from datetime import datetime
from functools import cached_property
from http.cookies import Morsel, SimpleCookie

from proper.constants import DELETE, GET, HEAD, PATCH, POST, PUT
from proper.errors import InvalidHeader
from proper.helpers import format_locale, parse_http_date, tunnel_decode

from .forwarded import parse_forwarded


DEFAULT_PORT = 80
DEFAULT_HTTPS_PORT = 443

MIME_ALL = "*/*"


def enc(name: str) -> str:
    return name.strip().lower().replace("-", "_")


class RequestHeadersMixin:
    """Mixin with the methods related to the request headers.
    """

    default_format = "html"

    env: dict[str, t.Any]

    def __init__(self, env: dict[str, t.Any]):
        self._normalize_env(env)

        self.protocol = self.env.get(
            "x_forwarded_proto",
            self.env.get("wsgi.url_protocol")
        )
        host, port = parse_host(self.env.get("host"))
        self.host = host
        self.port = port or self.default_port

        self.method = self.env.get("request_method", GET).upper()
        self.request_method = self.method

        # PATH_INFO is always "bytes tunneled as latin-1" and must be decoded back.
        path_info = self.env.get("path_info", "").strip("/")
        self.path = "/" + tunnel_decode(path_info)

        self.content_type = self.env.get("content_type", "")

        try:
            self.content_length = int(self.env.get("content_length") or "0")
        except ValueError:
            raise InvalidHeader("The Content-Length header must be a number.") from None
        if self.content_length < 0:
            raise InvalidHeader(
                "The value of the Content-Length header must be a positive number."
            )

    def _normalize_env(self, env: dict[str, t.Any]) -> None:
        """Normalize the environment variables.

        Arguments:

        - env:
            A WSGI environment dict passed in from the server (See also PEP-3333).

        """
        self.env = {
            enc(name): value
            for name, value in env.items()
            if not name.startswith("HTTP_")
        }
        for name, value in env.items():
            if not name.startswith("HTTP_"):
                continue
            name = enc(name).removeprefix("http_")
            if name in self.env:
                name = f"http_{name}"
            self.env[name] = value

    def get(self, name: str, default: t.Any = None) -> t.Any:
        name = enc(name)
        if name in (
            "accept",
            "accept_encoding",
            "accept_language",
            "cookie",
            "cookies",
            "date",
            "forwarded",
            "if_none_match",
            "if_modified_since",
            "request_id",
        ):
            value = getattr(self, name)
            return default if value is None else value

        return self.env.get(name, default)

    @property
    def headers(self) -> dict[str, t.Any]:
        return self.env

    @cached_property
    def accept(self) -> list[str]:
        """Parse the `accept` header.

        Indicates which content types, expressed as MIME types,
        the client is able to understand. Your app should select one of the proposals
        and informs the client of that choice with the `Content-Type`
        response header.

        Some examples of the `accept` header are:

        - text/html
        - text/html;level=1
        - text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
        - text/html;level=1,application/xhtml+xml;q=0.9,application/xml;q=0.8,*/*;q=0.7
        - text/html;level=1;q=0.9,application/xhtml+xml;q=0.8,application/xml;q=0.7,*/*;q=0.6

        Returns:
            A list of MIME types sorted by the quality value (q) in descending order.
            If no quality value is specified, the default value is 1.0.

        """
        return parse_accept(self.env.get("accept"))

    @cached_property
    def accept_encoding(self) -> list[str]:
        """Parse the `accept-encoding` header.

        Indicates the content encoding (usually a compression algorithm) that
        the client can understand. Your app should select one of the proposals
        and informs the client of that choice with the `Content-Encoding`
        response header.

        Some examples of the `accept-encoding` header are:

        - compress, gzip;q=0.5
        - deflate, gzip;q=1.0, *;q=0.5

        Returns:
            A list of encodings sorted by the quality value (q) in descending order.
            If no quality value is specified, the default value is 1.0.

        """
        return parse_accept(self.env.get("accept_encoding"))

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

        Some examples of the `accept-language` header are:

        - en-US,en;q=0.5
        - en-US,en;q=0.8,pt-BR;q=0.5,pt;q=0.3

        Returns:
            A list of languages sorted by the quality value (q) in descending order.
            If no quality value is specified, the default value is 1.0.

        """
        return parse_accept(self.env.get("accept_language"))

    @cached_property
    def cookie(self) -> dict[str, Morsel]:
        """Parse the `cookie` header.

        Returns:
            A dictionary with the cookies.

        """
        return parse_cookie(self.env.get("cookie"))

    @property
    def cookies(self) -> dict:
        """Parse the `cookie` header.

        An alias to `cookie`.
        """
        return self.cookie

    @cached_property
    def date(self) -> datetime | None:
        """Parse the `date` header.

        The date and time at which the message originated.

        Returns:
            A datetime object or None if the header is not present.

        """
        val = self.env.get("date")
        return parse_http_date(val)

    @property
    def default_port(self) -> int:
        """Returns the default port for the protocol of this request.
        """
        return DEFAULT_HTTPS_PORT if self.protocol == "https" else DEFAULT_PORT

    @cached_property
    def format(self) -> str:
        """Parse the `accept` header and try to return the default extension
        (for example: html, json, etc.) for the first mimetype of the list
        that has one.

        Some examples of the `format` header are:

        - text/html -> html
        - application/json -> json

        Returns:
            A string with the extension or the default format.

        """
        val = None
        for mime in self.accept:
            if mime == MIME_ALL:
                break
            ext = mimetypes.guess_extension(mime)
            if ext:
                val = ext[1:]
                break
        return val or self.default_format

    @cached_property
    def forwarded(self) -> list[dict[str, str]]:
        """Parse the `forwarded` header.

        The `Forwarded` header is a comma-separated list of forwarding
        information from the client to the server on its way through proxies.

        Returns:
            A list of dictionaries with the forwarding information.

        """
        return parse_forwarded(self.env.get("forwarded"))

    @property
    def host_with_port(self) -> str:
        """Returns a host:port string for this request, such as “example.com” or
        “example.com:8080”.

        Port is only included if it is not a default port (80 or 443)
        """
        return f"{self.host}{self.port_string}"

    @property
    def if_none_match(self) -> list[str]:
        """Parse the `if-none-match` header.

        The `If-None-Match` header makes the request conditional: if the
        requested variant has not changed since the time specified in this field,
        an entity will not be returned from the server; instead, a 304 (not
        modified) response will be returned without any message-body.

        Some examples of the `if-none-match` header values are:

        - "xyzzy"`
        - "xyzzy", "r2d2xxxx", "c3piozzzz"`
        - *

        Returns:
            A list of ETags.

        """
        return parse_comma_separated(self.env.get("if_none_match"))

    @cached_property
    def if_modified_since(self) -> datetime | None:
        """Parse the `if-modified-since` header.

        The `If-Modified-Since` header makes the request conditional: if the
        requested variant has not been modified since the time specified in this
        field, an entity will not be returned from the server; instead, a 304
        (not modified) response will be returned without any message-body.

        Returns:
            A datetime object or None if the header is not present.

        """
        val = self.env.get("if_modified_since")
        return parse_http_date(val)

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
        return self.env.get("x_requested_with") == "XMLHttpRequest"

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

        Returns:
            A string with the IP address.

        """
        for fw in self.forwarded:
            if "for" in fw:
                return fw["for"]

        ff = self.env.get("x_forwarded_for", "").split(",")[0]
        if ff:
            return ff

        realip = self.env.get("x_real_ip")
        if realip:
            return realip

        return self.env.get("remote_addr", "")

    @cached_property
    def request_id(self) -> str | None:
        """Parse the `x-request-id` header.

        This header is used to uniquely identify a request.

        Returns:
            A string with the request ID or None if the header is not present.

        """
        val = self.env.get("x_request_id")
        return parse_request_id(val)


# --- Parsers -----


def parse_accept(value: str | None) -> list[str]:
    """Parse an `accept`, `accept-encoding`, or a `accept-language` header.

    Returns:
        A list of values sorted by weight, in descending order.

    """
    if value is None:
        return []

    values = parse_multivalue(value)
    # Sorted by weight, in descending order
    ranking = sorted(
        [
            (
                format_locale(label),
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
    """Parse a comma-separated list of values."""
    if value is None:
        return []

    return RX_COMMA.split(value.strip(" ,"))


def parse_cookie(value: str | None) -> dict[str, Morsel]:
    """Parse a cookie header.

    Returns:
        A dictionary of cookies.

    """
    if value is None:
        return {}

    cookie = SimpleCookie()
    cookie.load(value)
    return cookie


def parse_host(value: str | None) -> tuple[str, int]:
    """Parse a host header.

    Returns:
        A tuple of (host, port) where port is 0 if not specified.

    """
    if not value:
        return "", 0

    host = value
    sport = ""

    if "]:" in value:
        host, sport = value.rsplit("]:", 1)
        host = host[1:]
    elif host[0] == "[":
        host = host[1:-1]
    elif ":" in host:
        host, sport = value.rsplit(":", 1)

    port = int(sport) if sport and sport.isdecimal() else 0
    return host, port


#: Header tokenizer used by parse_multivalue()
RX_SPLIT = re.compile('(?:(?:"((?:[^"\\\\]|\\\\.)*)")|([^;,=]+))([;,=]?)').findall


def parse_multivalue(header: str) -> list[tuple[str, dict]]:
    """Parses a typical multi-valued and parametrised HTTP header
    (e.g. Accept headers) and returns a list of values and parameters.
    For non-standard or broken input, this implementation may return partial results.

    Arguments:

    - header:
        A header string (e.g. `text/html,text/plain;q=0.9,*/*;q=0.8`)

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
    """Parse a request ID.

    This function will remove non-ASCII characters and truncate the
    request ID to 200 characters.

    Arguments:

    - val:
        The request ID.

    Returns:

    The parsed request ID or None if the input is None.

    """
    if val is None:
        return None
    val = str(val)[:REQUEST_ID_MAX_LENGTH]
    return RX_NON_ASCII.sub("", val)
