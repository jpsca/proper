from .base import Base
from .mixins import Authenticable


class User(Authenticable, Base):
    __repr_by__ = ["login"]

    @property
    def email(self):
        return self.login
