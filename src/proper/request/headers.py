import re
import typing as t
from datetime import datetime
from http.cookies import Morsel, SimpleCookie

from proper.helpers import InmutableDictMixin


class RequestHeaders(InmutableDictMixin):
    """A nicer way to handle WSGI headers
    """
    def __init__(self, headers):
        self._cache = {}
        super().__init__(headers)

    def __getitem__(self, key: str) -> t.Any:
        return self.get(key)

    def get(self, name: str, default: t.Any = None) -> t.Any:
        name = name.strip().lower().replace("-", "_").removeprefix("http_")
        value = self._parse(name)
        return default if value is None else value

    def _parse(self, name: str) -> t.Any:
        if name not in self._cache:
            self._cache[name] = parse_header(name, self.get(name))
        return self._cache[name]


RX_COMMA = re.compile(r",\s*")


def parse_header(name: str, value: t.Any) -> t.Any:
    if value is None:
        return None

    if name in ("accept", "accept_encoding", "accept_language"):
        return parse_accept(value)
    if name in ("if_none_match", ):
        return parse_comma_separated(value)
    elif name == "cookie":
        return parse_cookie(value)
    elif name == "host":
        return parse_host(value)
    elif name == "if_modified_since":
        return parse_if_modified_since(value)
    else:
        return value


def parse_accept(value: str) -> list[str]:
    values = _parse_multivalue(value)

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


def parse_comma_separated(value: str) -> list[str]:
    return RX_COMMA.split(value.strip(" ,"))


def parse_cookie(value: str) -> dict[str, Morsel]:
    cookie = SimpleCookie()
    cookie.load(value)
    return cookie


def parse_host(value: str) -> tuple[str, int]:
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


def parse_if_modified_since(value: str) -> datetime | None:
    """Parse a datetime from a header. Ignores obsoletes formats."""
    sdate = value.split(",", 1)[-1].strip()
    try:
        return datetime.strptime(sdate, "%d %b %Y %H:%M:%S %Z")
    except Exception:
        return None


# ---------------------------------------------------------------------------


#: Header tokenizer used by _parse_multivalue()
rx_split = re.compile('(?:(?:"((?:[^"\\\\]|\\\\.)*)")|([^;,=]+))([;,=]?)').findall


def _parse_multivalue(header: str) -> list[tuple[str, dict]]:
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
        for quoted, plain, tok in rx_split(header):
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
