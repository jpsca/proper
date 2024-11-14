import peewee as pw

from app.main import app
from .base import BaseModel


class Attachment(app.storage.Attachment, BaseModel):
    ...
