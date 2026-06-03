from datetime import datetime


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def format_http_date(dt: datetime) -> str:
    fmt = f"{DAYS[dt.weekday()]}, %d {MONTHS[dt.month - 1]} %Y %H:%M:%S GMT"
    return dt.strftime(fmt)


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



