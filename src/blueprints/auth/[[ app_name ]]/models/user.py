from ..app import db
from .concerns import Authenticable, Timestamped


class User(Authenticable, Timestamped, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
