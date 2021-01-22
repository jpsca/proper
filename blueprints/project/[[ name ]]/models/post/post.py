from hashlib import md5
from time import time

from ..base import Base, db
from ..mixins import Sluggable, utcnow

from .markdowner import convert_markdown
from .post_queries import PostQueries


class Post(PostQueries, Sluggable, Base):
    __tablename__ = "posts"
    __repr_attrs__ = ("title", )

    _sluggable_field = "title"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.Text, nullable=False)
    uid = db.Column(db.Text, nullable=False, unique=True)
    raw = db.Column(db.Text)
    html = db.Column(db.Text, nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    published_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    is_draft = db.Column(db.Boolean, nullable=False, default=True)

    topics = db.relationship(
        "Topic",
        lazy="select",
        secondary="posts_topics"
    )

    type = db.Column(db.String(10))
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "post"
    }

    @property
    def published_at_iso(self):
        return self.published_at.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def new_uid():
        return md5(str(int(time() * 1000)).encode()).hexdigest()

    @classmethod
    def create(cls, title, **attrs):
        attrs.setdefault("uid", Post.new_uid())

        raw = attrs.pop("raw", "").strip()
        html = attrs.get("html", "").strip()
        if raw and not html:
            html = convert_markdown(raw)

        if "description" not in attrs:
            attrs["description"] = raw[:256]
            if len(raw) > 256:
                attrs["description"] += "..."

        obj = cls(title=title, raw=raw, html=html, **attrs)
        db.add(obj)
        db.commit()
        return obj


class Quote(Post):
    __mapper_args__ = {
        "polymorphic_identity": "quote"
    }

    source_author = db.Column(db.Text)
    source_url = db.Column(db.Text)
    source = db.Column(db.Text)
