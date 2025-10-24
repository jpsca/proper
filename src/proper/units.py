from datetime import timedelta


__all__ = (
    "B",
    "KB",
    "MB",
    "GB",
    "TB",
    "SECONDS",
    "MINUTES",
    "HOURS",
    "DAYS",
    "WEEKS",
    "to_seconds",
)

B: int = 1  # bytes
KB: int = 2**10  # kilobytes
MB: int = 2**20  # megabytes
GB: int = 2**30  # gigabytes
TB: int = 2**40  # terabytes

SECONDS: int = 1
MINUTES: int = 60
HOURS: int = 60 * MINUTES
DAYS: int = 24 * HOURS
WEEKS: int = 7 * DAYS


def to_seconds(**kwargs) -> int:
    return int(timedelta(**kwargs).total_seconds())
