from datetime import datetime

import peewee as pw

from .base import BaseModel
from .concerns.authenticable import Authenticable


class User(Authenticable, BaseModel):
    created_at = pw.DateTimeField(default=datetime.utcnow)
