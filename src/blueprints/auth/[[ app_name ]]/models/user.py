from datetime import datetime

from peewee import *  # noqa

from .base import BaseModel
from .concerns import Authenticable


class User(Authenticable, BaseModel):
    created_at = DateTimeField(default=datetime.utcnow)

    def __init__(self, **kwargs):
        if "login" in kwargs:
            self.set_login(kwargs.pop("login"))
        if "password" in kwargs:
            self.set_password(kwargs.pop("password"))
        super().__init__(**kwargs)
