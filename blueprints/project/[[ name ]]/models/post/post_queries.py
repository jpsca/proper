from ..base import db


NUM_LATEST_POSTS = 1000

class PostQueries:

    @classmethod
    def latest(cls):
        return (
            db.query(cls)
            .filter_by(is_draft=False)
            .order_by(cls.published_at.desc())
            .limit(NUM_LATEST_POSTS)
        )
