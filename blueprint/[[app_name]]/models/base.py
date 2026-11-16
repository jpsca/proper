import typing as t

import peewee as pw
from proper.models import ProperModel, utcnow

from ..main import app


db = app.db["main"]


class _MainDatabase:
    database = db


# `Meta` is typed as `Any`: peewee removes it from the class it is defined in
# and every model declares its own, which a type checker reads as an override.
class BaseModel(ProperModel):
    Meta: t.Any = _MainDatabase

    created_at = pw.DateTimeField(default=utcnow)
