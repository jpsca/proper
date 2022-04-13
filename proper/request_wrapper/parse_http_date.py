from datetime import datetime
from typing import Optional


__all__ = ("parse_http_date",)


def parse_http_date(http_date: str) -> Optional[str]:
    """Parse a datetime from a header. Ignores obsoletes formats."""
    if not http_date:
        return None
    try:
        return datetime.strptime(http_date, "%a, %d %b %Y %H:%M:%S %Z")
    except Exception:
        return None
