import peewee as pw

from app.main import app
from .base import BaseModel


class Attachment(app.storage.Attachment, BaseModel):
    # You can add any extra fields here, like:
    # user = pw.ForeignKeyField(User, null=True)
    # etc.
    ...
