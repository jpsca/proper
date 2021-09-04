from sqlalchemy import *  # noqa
from sqlalchemy.orm import *  # noqa

from .base import Base
from .mixins import Authenticable, Timestamped


class User(Authenticable, Timestamped, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
