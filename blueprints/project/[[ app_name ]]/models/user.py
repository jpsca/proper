from .base import Base, db
from .mixins import Authenticable


class User(Authenticable, Base):
    __repr_attrs__ = ("login", )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=True)
    bio = db.Column(db.Text, nullable=True)

    @property
    def email(self):
        return self.login
