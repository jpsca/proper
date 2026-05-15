from datetime import timedelta


__all__ = (
    "B",
    "KB",
    "MB",
    "GB",
    "TB",
    "SECOND",
    "SECONDS",
    "MINUTE",
    "MINUTES",
    "HOUR",
    "HOURS",
    "DAY",
    "DAYS",
    "WEEK",
    "WEEKS",
    "MONTH",
    "MONTHS",
    "YEAR",
    "YEARS",
    "to_seconds",
)

B: int = 1  # bytes
KB: int = 2**10  # kilobytes
MB: int = 2**20  # megabytes
GB: int = 2**30  # gigabytes
TB: int = 2**40  # terabytes

SECOND: int = 1
SECONDS: int = 1
MINUTE: int = 60
MINUTES: int = MINUTE
HOUR: int = 60 * MINUTES
HOURS: int = HOUR
DAY: int = 24 * HOURS
DAYS: int = DAY
WEEK: int = 7 * DAYS
WEEKS: int = WEEK
MONTH: int = 30 * DAYS  # approx
MONTHS: int = MONTH
YEAR: int = 365 * DAYS  # approx
YEARS: int = YEAR


def to_seconds(**kwargs) -> int:
    return int(timedelta(**kwargs).total_seconds())
