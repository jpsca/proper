from .base import Base, db
from .mixins import Sluggable


class Topic(Sluggable, Base):
    __repr_attrs__ = ("name", )

    _sluggable_field = "name"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)

    posts = db.relationship(
        "Post",
        lazy="select",
        secondary="posts_topics"
    )
