import peewee as pw

from .base import BaseModel, utcnow
from .concerns.authenticable import Authenticable


class User(Authenticable, BaseModel):
    created_at = pw.DateTimeField(default=utcnow)
