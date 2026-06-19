from datetime import datetime, timedelta

import peewee as pw
import pytest


db = pw.SqliteDatabase(":memory:")


class Post(pw.Model):
    id = pw.AutoField()
    title = pw.CharField()
    created_at = pw.DateTimeField()

    class Meta:
        database = db


def _seed(count):
    base = datetime(2020, 1, 1, 12, 0, 0)
    rows = [
        {
            "title": f"Post {i}",
            # created_at deliberately collides (i % 50) so tests exercise the
            # id tie-breaker in the keyset ordering.
            "created_at": base + timedelta(minutes=i % 50),
        }
        for i in range(1, count + 1)
    ]
    Post.insert_many(rows).execute()


@pytest.fixture
def make_posts():
    db.connect(reuse_if_open=True)
    db.create_tables([Post])

    def factory(count):
        _seed(count)
        return Post

    yield factory
    db.drop_tables([Post])
    db.close()


@pytest.fixture
def posts(make_posts):
    return make_posts(100)
