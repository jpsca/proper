from datetime import datetime

from peewee import DateTimeField

from .base import BaseModel
from .concerns.authenticable import Authenticable


class User(Authenticable, BaseModel):
    created_at = DateTimeField(default=datetime.utcnow)
