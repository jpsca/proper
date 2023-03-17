import typing as t
from datetime import date, datetime
from hashlib import sha1

from proper.errors import InvalidHeader
from proper.helpers import tunnel_encode


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def enc_name(name: str) -> str:
    name = name.strip().lower().replace("-", "_").removeprefix("http_")
    if not name.isascii():
        raise InvalidHeader("A header name must be encodable as ASCII")
    return name


class ResponseHeaders(dict):
    """Response headers.
    """

    def __setitem__(self, name: str, value: t.Any):
        self.set(name, value)

    def add(self, name: str, value: str):
        self.setdefault(name, []).append(value)

    def set(self, name: str, value: str):
        self[name] = [value]

    def get(self, name: str, default: t.Any = None) -> str:
        values = super().get(name)
        if values is None:
            return default
        return ", ".join(values)

    def get_tuples(self, exclude: list[str] | None = None) -> list[tuple[bytes, str]]:
        exclude = [enc_name(name) for name in exclude or []]
        return [
            (
                name.replace("_", "-").encode("ascii"),
                tunnel_encode(", ".join(values), "utf-8")
            )
            for name, values in self.items()
            if name not in exclude
        ]


class ResponseHeadersMixin:
    """Mixin with the methods related to the response headers.
    """

    def __init__(self) -> None:
        self._headers = ResponseHeaders()

    @property
    def headers(self):
        return self._headers.copy()

    def get_header(self, name: str, default: t.Any = None) -> str:
        name = enc_name(name)
        return self._headers.get(name, default)

    def set_headers(self, headers: t.Iterable[tuple[str, str]]) -> None:
        for name, coded_value in headers:
            name = enc_name(name)
            self.set_header(name, coded_value)

    def set_header(self, name: str, value: t.Any, **params) -> None:
        """Set a response header"""
        name = enc_name(name)

        callable_setter = getattr(self, f"set_{name}", None)
        if callable_setter and callable(callable_setter):
            callable_setter(value, **params)
        elif hasattr(self, name):
            setattr(self, name, value)
        else:
            coded_value = format_generic_header(value, **params)
            self._headers.set(name, coded_value)

    @property
    def etag(self) -> str:
        return self._headers.get("etag")

    @etag.setter
    def etag(self, etag: date | int | float | str):
        self.set_etag(etag)

    def set_etag(self, etag: date | int | float | str, *, strong: bool = False) -> None:
        """
        Sets the Etag header.

        The Etag can be generated from a date, a string or a number.

        Arguments:
            - strong:
                By default a “weak” Etag is used. Set this to `True` to set a
                “strong” ETag validator on the response. A strong ETag implies
                exact equality: the response must match byte for byte.
                This is necessary for doing range requests within a large file
                or for compatibility with some CDNs that don’t support weak ETags.

        """
        assert etag is not None
        # not md5 because is not availabe in some systems
        digest = sha1(str(etag).encode()).hexdigest()
        coded_value = f'"{digest}"' if strong else f'W/"{digest}"'
        self._headers["etag"] = coded_value

    @property
    def last_modified(self) -> str:
        return self._headers.get("last-modified")

    @last_modified.setter
    def last_modified(self, dt: date | float | int) -> None:
        """
        Sets the Last-Modified header.

        The Last-Modified can be generated from a timestamp of rom an UTC or naive datetime.
        """
        assert dt is not None
        if isinstance(dt, (float, int)):
            dt = datetime.utcfromtimestamp(dt)
        self._last_modified = dt
        fmt = f"{DAYS[dt.weekday()]}, %d {MONTHS[dt.month - 1]} %Y %H:%M:%S GMT"
        self._headers["last-modified"] = dt.strftime(fmt)


def format_header_value(value, **params) -> str:
    """Takes a value and a list of parameters and returns a valid header value.
    """
    if params:
        return f"{value}; {'; '.join(f'{k}={v}' for k, v in params.items())}"
    return str(value)
