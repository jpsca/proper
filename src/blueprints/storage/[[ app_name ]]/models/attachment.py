from datetime import datetime

from peewee import *  # noqa

from ..app import app
from .base import BaseModel


class Attachment(app.storage.Attachment, BaseModel):
    created_at = DateTimeField(default=datetime.utcnow)
