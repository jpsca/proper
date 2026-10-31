import typing as t
from datetime import datetime, timezone

import peewee as pw

from proper import ProperModel, scope  # noqa
from ..main import app


db = app.db["main"]


def utcnow() -> datetime:
    """The naive UTC datetime peewee's `utcnow` returns, with a type."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class _MainDatabase:
    database = db


# `Meta` is typed as `Any`: peewee removes it from the class it is defined in
# and every model declares its own, which a type checker reads as an override.
class BaseModel(ProperModel):
    Meta: t.Any = _MainDatabase

    created_at = pw.DateTimeField(default=utcnow)
