from .base import Base, db
from .mixins import Authenticable, Timestamped


class User(Authenticable, Timestamped, Base):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
