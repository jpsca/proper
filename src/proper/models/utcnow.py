from datetime import datetime, timezone


def utcnow() -> datetime:
    """The naive UTC datetime peewee's `utcnow` returns, with a type."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
