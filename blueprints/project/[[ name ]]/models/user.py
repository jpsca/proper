from datetime import datetime

from pony.orm import Required, Optional

from ..db import db

from .concerns.authenticable import AuthenticableMixin


class User(AuthenticableMixin, db.Entity):
    login = Required(str, unique=True)
    password = Optional(str)
    last_sign_in = Optional(datetime)

    def before_update(self):
        super().before_update()
