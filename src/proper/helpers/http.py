"""
When a request comes in, web servers decode some fields like the path.
The decoded path may contain UTF-8 characters but, according to the WSGI spec,
no strings can contain chars outside ISO-8859-1.

To reconcile the URI encoding standard that allows UTF-8 with the WSGI spec
that does not, WSGI servers tunnel the string via ISO-8859-1. Theses functions
does that:

    >>> tunnel_encode('olé')
    'olÃ©'

    >>> tunnel_decode('olÃ©')
    'olé'

"""
from datetime import datetime


__all__ = (
    "parse_http_date",
    "format_http_date",
    "tunnel_encode",
    "tunnel_decode",
    "format_locale",
    "split_locale",
)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def parse_http_date(value: str | None) -> datetime | None:
    """Parse a datetime from a header. Ignores obsoletes formats."""
    if value is None:
        return None

    sdate = value.split(",", 1)[-1].strip()
    try:
        return datetime.strptime(sdate, "%d %b %Y %H:%M:%S %Z")
    except Exception:
        return None


def format_http_date(dt: datetime) -> str:
    fmt = f"{DAYS[dt.weekday()]}, %d {MONTHS[dt.month - 1]} %Y %H:%M:%S GMT"
    return dt.strftime(fmt)


def tunnel_encode(string: str, charset: str = "utf8") -> str:
    return string.encode(charset).decode("iso-8859-1")


def tunnel_decode(string: str, charset: str = "utf8") -> str:
    return string.encode("iso-8859-1").decode(charset, "replace")


def format_locale(locale: str) -> str:
    return "_".join(split_locale(locale))


def split_locale(locale: str) -> tuple[str] | tuple[str, str]:
    """Returns a tuple (language, territory) from a string
    like 'en', 'en-US', 'en_US', etc.
    """
    tloc = locale.replace("-", "_").lower().strip().split("_")
    if len(tloc) > 1:
        return (tloc[0], tloc[1].upper())
    return (tloc[0], )
