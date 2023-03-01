from datetime import datetime

from peewee import *  # noqa

from .base import BaseModel
from .concerns import Authenticable


class User(Authenticable, BaseModel):
    created_at = DateTimeField(default=datetime.utcnow)
