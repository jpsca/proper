import typing as t
from datetime import date, datetime
from hashlib import sha1

from proper.errors import InvalidHeader
from proper.helpers import tunnel_encode


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def enc_name(name: str) -> str:
    name = name.strip().lower().replace("_", "-").removeprefix("http_")
    if not name.isascii():
        raise InvalidHeader("A header name must be in ASCII")
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
                name.encode("ascii"),
                tunnel_encode(", ".join(values), "utf-8")
            )
            for name, values in self.items()
            if name not in exclude
        ]


class ResponseHeadersMixin:
    """Mixin with the methods related to the response headers.
    """

    # Cache
    _etag: str | None = None
    _last_modified: date | None = None

    def __init__(self) -> None:
        self._headers = ResponseHeaders()

    def get(self, name: str, default: t.Any = None) -> str:
        name = enc_name(name)
        return self._headers.get(name, default)

    def set(self, name: str, value: t.Any, **params) -> None:
        """Set a response header"""
        name = enc_name(name)

        if name == "etag":
            self.set_etag(value, **params)
        elif name == "last-modified":
            self.set_last_modified(value, **params)
        else:
            self._headers[name] = str(value)

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
        value = f'"{digest}"' if strong else f'W/"{digest}"'
        self._headers["etag"] = value
        self._etag = value

    def set_last_modified(self, dt: date | float | int) -> None:
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


    # def _segment_to_str(self, value: str | None, params: dict[str, t.Any]) -> str:
    #     """Produce a header value and `key=value` parameters separated by semicolons.

    #     If a value contains non-token characters, it will be quoted.
    #     If a value is `None`, the parameter is skipped.
    #     In some keys for some headers, a UTF-8 value can be encoded using a special
    #     `key*=UTF-8''value` form, where `value` is percent encoded. This function will
    #     not produce that format automatically, but if a given key ends with an asterisk
    #     `*`, the value is assumed to have that form and will not be quoted further.
    #     If a key ends with `*`, its value will not be quoted.

    #     """
    #     segments = []
    #     if value is not None:
    #         segments.append(value)

    #     for key, value in params.items():
    #         if value is None:
    #             continue
    #         if key[-1] == "*":
    #             segments.append(f"{key}={value}")
    #         else:
    #             value = self._quote_value(value)
    #             segments.append(f"{key}={value}")

    #     return ";".join(segments)

    # def _quote_value(self, value: str) -> str:
    #     """Add double quotes around a header value. If the header contains
    #     only ASCII token characters, it will be returned unchanged.
    #     If the header contains ``"`` or ``\\`` characters, they will be escaped
    #     with an additional ``\\`` character.
    #     """
    #     if not value:
    #         return '""'

    #     if " " in value or "\\" in value or '"' in value:
    #         value = value.replace("\\", "\\\\").replace('"', '\\"')
    #         return f'"{value}"'

    #     return value

    # cookies
    #     return [
    #         tuple(morsel.output().split(": ", 1))
    #         for morsel in self.cookies.values()
    #     ]
