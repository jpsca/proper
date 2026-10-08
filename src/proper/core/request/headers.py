import ipaddress
import mimetypes
import re
import typing as t
from datetime import datetime, timezone
from functools import cached_property
from http import cookies as http_cookies

from dateutil.parser import parse as dtparse

from ...constants import DELETE, GET, HEAD, PATCH, POST, PUT, TURBO_STREAM_MIME
from ...errors import InvalidHeader
from ...helpers import MultiDict
from ...helpers.formatters import format_locale
from ..config import DEFAULT_TRUSTED_PROXIES, parse_trusted_proxies
from .forwarded import parse_forwarded


class RequestHeadersMixin:
    """Mixin with the methods related to the request headers.
    """

    app: t.Any
    headers: MultiDict
    method: str
    request_method: str
    scheme: str
    server: "tuple[str, int | None] | None"
    client: "tuple[str, int | None] | None"
    default_format = "html"

    def __init__(self):
        forwarded_proto = self.headers.get("x-forwarded-proto")
        self.protocol: str = (
            forwarded_proto
            if forwarded_proto and self._from_trusted_proxy
            else self.scheme
        )

        # As PEP 3333 rebuilds the URL: the `Host` header, else the address
        # the request arrived at. That address is where the server listens
        # (`0.0.0.0`, or a Unix socket), not the name the client asked for.
        # Repeated lines are joined with commas, as the server does, so
        # they are a 400 (RFC 9112 §3.2).
        host_header = self._combined("host")
        if host_header:
            host, port = parse_host(host_header)
            host = host.lower()
        elif self.server:
            host, port = self.server
        else:
            host, port = "", 0
        self.host: str = host
        self.port: int = port or self.default_port

        self.content_type: str = self.headers.get("content-type")
        try:
            self.content_length: int = int(self.headers.get("content-length") or "0")
        except ValueError:
            raise InvalidHeader("The Content-Length header must be a number.") from None
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
        return parse_accept(self.headers.get("accept"))

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
        return parse_accept(self.headers.get("accept-encoding"))

    @cached_property
    def accept_language(self) -> list[str]:
        """Parse the `accept-language` header.

        Indicates the natural language and locale that the client prefers.
        Your app should select one of the proposals and informs the client
        of that choice with the `Content-Language` response header.

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
        return parse_accept(self.headers.get("accept-language"), is_language=True)


    @property
    def cookie(self) -> dict[str, str]:
        """An alias to `cookies`.
        """
        return self.cookies

    @cached_property
    def cookies(self) -> dict:
        """Parse the `cookie` header.

        Returns:
            A dictionary with the cookies.

        """
        cookies: dict[str, str] = {}
        cookie_headers = self.headers.getall("cookie")
        for header in cookie_headers:
            if isinstance(header, bytes):
                header = header.decode("utf-8", errors="ignore")
            cookies.update(parse_cookie(header))
        return cookies

    @cached_property
    def date(self) -> datetime | None:
        """Parse the `date` header.

        The date and time at which the message originated.

        Returns:
            A datetime object, or None if the header is not present or is
            not a valid date.

        """
        return parse_date(self.headers.get("date"))

    @property
    def default_port(self) -> int:
        """Returns the default port for the protocol of this request.
        """
        return 443 if self.protocol == "https" else 80

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
            if mime == "*/*":
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

        This is the header as it arrived, whoever sent it: any client can
        write one. `remote_ip` uses it only when the request comes from a
        trusted proxy (`TRUSTED_PROXIES`).

        Returns:
            A list of dictionaries with the forwarding information.

        """
        return parse_forwarded(self._combined("forwarded"))

    @property
    def host_with_port(self) -> str:
        """Returns a host:port string for this request, such as “example.com” or
        “example.com:8080”: the netloc of its URL, so an IPv6 address is in
        brackets, as in the `Host` header (“[2001:db8::1]:8080”).

        Port is only included if it is not a default port (80 or 443)
        """
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{host}{self.port_string}"

    @property
    def if_none_match(self) -> list[str]:
        """Parse the `if-none-match` header.

        The `If-None-Match` header makes the request conditional: if the
        requested variant has not changed since the time specified in this field,
        an entity will not be returned from the server; instead, a 304 (not
        modified) response will be returned without any message-body.

        Some examples of the `if-none-match` header values are:

        - "xyzzy"
        - "xyzzy", "r2d2xxxx", "c3piozzzz"
        - *

        Returns:
            A list of ETags.

        """
        return parse_comma_separated(self.headers.get("if-none-match"))

    @cached_property
    def if_modified_since(self) -> datetime | None:
        """Parse the `if-modified-since` header.

        The `If-Modified-Since` header makes the request conditional: if the
        requested variant has not been modified since the time specified in this
        field, an entity will not be returned from the server; instead, a 304
        (not modified) response will be returned without any message-body.

        Returns:
            A datetime object, or None if the header is not present or is
            not a valid date (RFC 9110 says to ignore it then).

        """
        return parse_date(self.headers.get("if-modified-since"))

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

    @cached_property
    def _from_trusted_proxy(self) -> bool:
        """True if the peer that sent this request (the `client` address)
        is one of the `TRUSTED_PROXIES`, so its forwarding headers
        (`X-Forwarded-For`, `Forwarded`, `X-Real-IP` and
        `X-Forwarded-Proto`) can be believed.

        A request without a peer address also counts, as in Rack: Granian
        or gunicorn listening on a Unix socket, which only a process on the
        same machine (such as nginx) can connect to, give an empty
        `REMOTE_ADDR`. A peer `unix:...` counts too.
        """
        peer = self.client[0] if self.client else ""
        if not peer or peer == "unix" or peer.startswith("unix:"):
            return True
        return is_trusted_proxy(peer, self._trusted_proxies())

    def _trusted_proxies(self) -> "TNetworks":
        app = self.app
        if not app:
            return DEFAULT_TRUSTED_PROXIES
        trusted = app.config.TRUSTED_PROXIES
        # Parsed when the app is created; parsed here if it was set later.
        if all(isinstance(network, IPNetwork) for network in trusted):
            return trusted
        return parse_trusted_proxies(trusted)

    @property
    def is_secure(self) -> bool:
        """True if the protocol is HTTPS.

        Behind a trusted proxy (`TRUSTED_PROXIES`), the protocol is the one
        in its `X-Forwarded-Proto` header."""
        return self.protocol == "https"

    is_ssl = is_secure

    @property
    def is_xhr(self) -> bool:
        """True if the request was done by JavaScript."""
        return self.headers.get("x-requested-with") == "XMLHttpRequest"

    @property
    def turbo_frame(self) -> "str | None":
        """The `Turbo-Frame` request header: the id of the frame Turbo is
        updating, or `None` for a full-page request. Branch on it to render a
        bare frame instead of the whole layout."""
        return self.headers.get("turbo-frame")

    @property
    def turbo_stream(self) -> bool:
        """True when the client accepts a Turbo Stream response (it sent the
        Turbo Stream MIME in its `Accept` header)."""
        return TURBO_STREAM_MIME in self.accept

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
        """IP address of the client.

        When the request comes from one of the `TRUSTED_PROXIES`, this is
        the address in its forwarding headers: `X-Forwarded-For`, else
        `Forwarded`, else `X-Real-IP`. Each proxy adds the address it got
        the request from at the end of the first two, so they are read
        from the right, skipping the trusted proxies: whatever is further
        left could have been written by the client. If every address is a
        trusted proxy, it is the leftmost one.

        `X-Forwarded-For` comes first because it is the one nearly every
        proxy writes; most pass a `Forwarded` header from the client
        through untouched. A header sent in several lines is read as one
        list, its lines joined in order (RFC 9110 §5.3).

        Otherwise, it is the address of the peer that sent the request
        and the forwarding headers are ignored, because any client can
        send them. A request without a peer address (Granian or gunicorn on
        a Unix socket) counts as coming from a trusted proxy.

        Returns:
            A string with the IP address, or `""` if there is none. An
            address from `X-Forwarded-For` or `Forwarded` is returned
            without its port and brackets (`[2001:db8::1]:4711` gives
            `2001:db8::1`), and an IPv4-mapped one (`::ffff:1.2.3.4`) as
            IPv4 (`1.2.3.4`). A value that is not an address is returned as
            written: an obfuscated identifier (`_hidden`, `unknown`).

        """
        peer = self.client[0] if self.client else ""
        if not self._from_trusted_proxy:
            return peer
        trusted = self._trusted_proxies()

        hops = [
            hop.strip() for hop in (self._combined("x-forwarded-for") or "").split(",")
        ]
        hops = [hop for hop in hops if hop]
        if not hops:
            # Each element is parsed on its own, so a quoted string that the
            # client leaves open can't take in the element that a trusted
            # proxy appends.
            hops = [
                fw["for"]
                for element in split_forwarded(self._combined("forwarded") or "")
                for fw in parse_forwarded(element)
                if "for" in fw
            ]
        if hops:
            hop = closest_untrusted_hop(hops, trusted)
            # Without the port that some proxies add (Azure Application
            # Gateway), which changes with each connection of the client.
            ip = parse_ip(hop)
            return str(ip) if ip else hop

        realip = self.headers.get("x-real-ip")
        if realip:
            return realip

        return peer

    def _combined(self, name: str) -> str | None:
        """The values of a list header sent in several field lines, joined
        with commas in the order they came, as RFC 9110 §5.3 combines them.
        `None` if the header isn't there."""
        values = self.headers.getall(name)
        return ",".join(values) if values else None

    @cached_property
    def request_id(self) -> str | None:
        """Parse the `x-request-id` header.

        This header is used to uniquely identify a request.

        Returns:
            A string with the request ID or None if the header is not present.

        """
        val = self.headers.get("x-request-id")
        return parse_request_id(val)

    @cached_property
    def user_agent(self) -> str | None:
        """Get the `user-agent` header.

        The `User-Agent` header contains a characteristic string that
        allows the network protocol peers to identify the application type,
        operating system, software vendor or software version of the requesting
        software user agent.

        Returns:
            A string with the user agent or None if the header is not present.

        """
        return self.headers.get("user-agent")


# --- Parsers ---


IPNetwork = (ipaddress.IPv4Network, ipaddress.IPv6Network)
TNetworks = tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]


def parse_ip(value: str) -> "ipaddress.IPv4Address | ipaddress.IPv6Address | None":
    """Parse the IP address of a `Forwarded` or `X-Forwarded-For` hop, or
    of the peer: `1.2.3.4`, `1.2.3.4:8080`, `2001:db8::1`, `[2001:db8::1]`
    or `[2001:db8::1]:4711`. An IPv4-mapped IPv6 address
    (`::ffff:1.2.3.4`) is returned as the IPv4 one.

    Returns:
        The address, or `None` if `value` is not one (e.g. `unknown`).

    """
    value = value.strip()
    if value.startswith("["):
        value = value[1:].partition("]")[0]
    elif value.count(":") == 1:
        value = value.partition(":")[0]
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None
    return getattr(ip, "ipv4_mapped", None) or ip


def is_trusted_proxy(value: str, trusted: TNetworks) -> bool:
    """True if `value` is an IP address in one of the `trusted` networks."""
    ip = parse_ip(value)
    return ip is not None and any(ip in network for network in trusted)


def closest_untrusted_hop(hops: list[str], trusted: TNetworks) -> str:
    """The rightmost of `hops` that isn't a trusted proxy, or the leftmost
    one if all of them are.

    A value that is not an IP address (`unknown`, `_hidden`) is not a
    trusted proxy: it is returned, and nothing at its left is read.
    """
    for hop in reversed(hops):
        if not is_trusted_proxy(hop, trusted):
            return hop
    return hops[0]


def split_forwarded(value: str) -> list[str]:
    """Split a `Forwarded` header into its elements: at the commas that are
    not inside a quoted string (`host="a,b"`).

    The header is read from the right, because the elements the trusted
    proxies append are there and are well formed: a quoted string that the
    client leaves open (`for="1.2.3.4`) takes in only what is at its left.
    """
    if '"' not in value:
        return value.split(",")
    elements = []
    end = len(value)
    in_quotes = False
    for pos in range(len(value) - 1, -1, -1):
        char = value[pos]
        if char == '"':
            # Inside a quoted string, `\"` is a quote, not its start.
            start = pos
            while start and value[start - 1] == "\\":
                start -= 1
            if not (in_quotes and (pos - start) % 2):
                in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            elements.append(value[pos + 1 : end])
            end = pos
    elements.append(value[:end])
    elements.reverse()
    return elements


def parse_date(value: str | None) -> datetime | None:
    """Parse a date header.

    The date and time at which the message originated.

    Returns:
        A datetime object in UTC, or None if the header is not present or
        is not a valid date.

    """
    if value is None:
        return None
    try:
        date = dtparse(value)
        # The super-old ANSI C's asctime() format doesn't include timezone
        # information, but the other formats do, so we assume UTC for it.
        if date.tzinfo is None:
            return date.replace(tzinfo=timezone.utc)
        # An OverflowError if the offset moves it out of datetime's range
        # (`Fri, 31 Dec 9999 23:59:59 -0100`).
        return date.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        # RFC 9110 §13.1.3: an invalid date is ignored.
        return None


def parse_accept(value: str | None, *, is_language: bool = False) -> list[str]:
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
                format_locale(label) if is_language else label,
                parse_qvalue(params.get("q")),
            )
            for label, params in values
        ],
        key=lambda tup: tup[1],
        reverse=True
    )
    # Return only the labels
    return [label for label, _ in ranking]


def parse_qvalue(value: str | None) -> float:
    """Parse the `q` parameter of an `accept*` header.

    Returns:
        The weight, from 0 to 1. It is 1 when there is no `q`, or when it
        is not a number from 0 to 1: a bad parameter is ignored.

    """
    try:
        weight = float(value or 1)
    except ValueError:
        return 1.0
    return weight if 0 <= weight <= 1 else 1.0


RX_COMMA = re.compile(r",\s*")


def parse_comma_separated(value: str | None) -> list[str]:
    """Parse a comma-separated list of values."""
    if value is None:
        return []

    return RX_COMMA.split(value.strip(" ,"))


def parse_cookie(cookie_string: str | None) -> dict[str, str]:
    """
    This function parses a `Cookie` HTTP header into a dict of key/value pairs.

    It attempts to mimic browser cookie parsing behavior: browsers and web servers
    frequently disregard the spec (RFC 6265) when setting and reading cookies,
    so we attempt to suit the common scenarios here.

    This function has been extracted from Starlette 1.0, which is based on Django's implementation,
    which in turn is based on Python's `http.cookies.SimpleCookie` implementation.

    Note: we are explicitly _NOT_ using `SimpleCookie.load`.
    """
    if cookie_string is None:
        return {}

    cookie_dict: dict[str, str] = {}
    for chunk in cookie_string.split(";"):
        if "=" in chunk:
            key, val = chunk.split("=", 1)
        else:
            # Assume an empty name per
            # https://bugzilla.mozilla.org/show_bug.cgi?id=169091
            key, val = "", chunk
        key, val = key.strip(), val.strip()
        if key or val:
            # unquote using Python's algorithm.
            cookie_dict[key] = http_cookies._unquote(val)
    return cookie_dict



# Host = uri-host [ ":" port ] per RFC 9112 §3.2 / RFC 3986 §3.2.2-3.2.3.
# uri-host is a bracketed IP-literal (IPv6), an IPv4 address, or a reg-name
# (unreserved / pct-encoded / sub-delims); the optional port is *DIGIT.
# What is in the brackets must also be an IPv6 address: `parse_host` checks
# it with `ipaddress` (so `[abc]` and `[1.2.3.4]` are refused). IPvFuture
# (`[v1.x]`) and an IPv6 zone id (RFC 6874) are refused too.
# The reg-name here has every sub-delim but the comma: a server joins the
# lines of a repeated `Host` header with commas (Granian 2.8.3 does), and a
# request with more than one `Host` line is a 400 (RFC 9112 §3.2). A host
# name (RFC 1123) has no comma.
# Anchored with \A...\Z (not ^...$) so a trailing newline can't sneak past.
RX_VALID_HOST = re.compile(
    r"\A"
    r"(?:"
    r"\[[0-9A-Fa-f:.]+\]"  # IP-literal (IPv6)
    r"|"
    r"(?:[A-Za-z0-9\-._~!$&'()*+;=]|%[0-9A-Fa-f]{2})+"  # IPv4 / reg-name
    r")"
    r"(?::[0-9]*)?"  # optional port
    r"\Z"
)


def parse_host(value: str | None) -> tuple[str, int]:
    """Parse a host header.

    Returns:
        A tuple of (host, port) where port is 0 if not specified.

    """
    if value is None:
        return "", 0

    if not value or RX_VALID_HOST.match(value) is None:
        raise InvalidHeader("The Host header contains invalid characters.")

    host = value
    sport = ""

    if value[0] == "[":
        host, _, sport = value[1:].partition("]")
        sport = sport[1:]
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            raise InvalidHeader(
                "The Host header has brackets around something that is not "
                "an IPv6 address."
            ) from None
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
        header:
            A header string (e.g. `text/html,text/plain;q=0.9,*/*;q=0.8`)

    Return:
        List of (value, params) tuples. The second element is a
        (possibly empty) dict. The parameter names are lowercased, because
        they are case-insensitive (RFC 9110 §5.6.6): `Q=0.5` is `q`.

    """
    values = []
    if '"' not in header:  # INFO: Fast path without regexp (~2x faster)
        for value in header.split(","):
            parts = value.split(";")
            values.append((parts[0].strip(), {}))
            for attr in parts[1:]:
                name, _, value = attr.partition("=")
                name = name.strip().lower()
                if name:
                    values[-1][1][name] = value.strip()
    else:
        lop, key, attrs = ",", None, {}
        for quoted, plain, tok in RX_SPLIT(header):
            value = plain.strip() if plain else quoted.replace('\\"', '"')
            if lop == ",":
                attrs = {}
                values.append((value, attrs))
            elif lop == ";":
                if tok == "=":
                    key = value.lower()
                else:
                    attrs[value.lower()] = ""
            elif lop == "=" and key:
                attrs[key] = value
                key = None
            lop = tok
    return values


REQUEST_ID_MAX_LENGTH = 200
RX_NON_ASCII = re.compile(r"[^\x00-\x7f]")


def parse_request_id(val: str | None) -> str | None:
    """Parse a request ID.

    This function will remove non-ASCII characters and truncate the
    request ID to 200 characters.

    Arguments:
        val:
            The request ID.

    Returns:
        The parsed request ID or None if the input is None.

    """
    if val is None:
        return None
    val = str(val)[:REQUEST_ID_MAX_LENGTH]
    return RX_NON_ASCII.sub("", val)
