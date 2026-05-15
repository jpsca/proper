import peewee as pw
from proper import ProperModel, scope  # noqa

from ..main import app


db = app.db["main"]


class BaseModel(ProperModel):
    class Meta:
        database = app.db["main"]
