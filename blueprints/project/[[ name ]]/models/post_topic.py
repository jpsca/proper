from .base import Base, db


class PostTopic(Base):
    __tablename__ = "posts_topics"

    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), primary_key=True)
