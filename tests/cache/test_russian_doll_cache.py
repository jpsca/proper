from time import sleep

import peewee as pw
import pytest


@pytest.fixture()
def RussianDollCached(BaseModel):
    # Reproduces the blueprint's RussianDollCached mixin for testing.
    class RussianDollCached(BaseModel):
        updated_at = pw.DateTimeField(default=pw.utcnow, null=True)
        touches: tuple[str, ...] = ()

        class Meta:
            table_name = None  # type: ignore

        @classmethod
        def update(cls, *args, **kwargs):
            kwargs["updated_at"] = pw.utcnow()
            return super().update(*args, **kwargs)

        def save(self, *args, **kwargs):
            self.updated_at = pw.utcnow()
            result = super().save(*args, **kwargs)
            self._touch_related()
            return result

        def delete_instance(self, *args, **kwargs):
            self._touch_related()
            return super().delete_instance(*args, **kwargs)

        def touch(self):
            type(self).update(updated_at=pw.utcnow()).where(
                type(self)._meta.primary_key == self.get_id()
            ).execute()
            self._touch_related()

        def _touch_related(self):
            for field_name in self.touches:
                related = getattr(self, field_name, None)
                if related is not None and hasattr(related, "touch"):
                    related.touch()

    return RussianDollCached


@pytest.fixture()
def Post(db, RussianDollCached):
    class Post(RussianDollCached):
        title = pw.TextField()

        class Meta:
            table_name = "posts"

    db.create_tables([Post])
    return Post


@pytest.fixture()
def Comment(db, RussianDollCached, Post):
    class Comment(RussianDollCached):
        post = pw.ForeignKeyField(Post, backref="comments")
        body = pw.TextField()
        touches = ("post",)

        class Meta:
            table_name = "comments"

    db.create_tables([Comment])
    return Comment


@pytest.fixture()
def Reply(db, RussianDollCached, Comment):
    class Reply(RussianDollCached):
        comment = pw.ForeignKeyField(Comment, backref="replies")
        body = pw.TextField()
        touches = ("comment",)

        class Meta:
            table_name = "replies"

    db.create_tables([Reply])
    return Reply


class TestTouches:
    def test_save_touches_parent(self, Post, Comment):
        post = Post.create(title="Hello")
        original_ts = post.updated_at

        sleep(0.01)
        Comment.create(post=post, body="Nice post")

        post = Post.get_by_id(post.id)
        assert post.updated_at > original_ts

    def test_delete_touches_parent(self, Post, Comment):
        post = Post.create(title="Hello")
        comment = Comment.create(post=post, body="Nice post")
        original_ts = Post.get_by_id(post.id).updated_at

        sleep(0.01)
        comment.delete_instance()

        post = Post.get_by_id(post.id)
        assert post.updated_at > original_ts

    def test_cascading_touch(self, Post, Comment, Reply):
        """Reply touches Comment, which touches Post (russian doll)."""
        post = Post.create(title="Hello")
        comment = Comment.create(post=post, body="Nice")
        original_post_ts = Post.get_by_id(post.id).updated_at
        original_comment_ts = Comment.get_by_id(comment.id).updated_at

        sleep(0.01)
        Reply.create(comment=comment, body="Thanks")

        post = Post.get_by_id(post.id)
        comment = Comment.get_by_id(comment.id)
        assert comment.updated_at > original_comment_ts
        assert post.updated_at > original_post_ts

    def test_no_touches_by_default(self, Post):
        """Models without `touches` don't touch anything."""
        post = Post.create(title="Hello")
        original_ts = post.updated_at

        sleep(0.01)
        post.title = "Updated"
        post.save()

        post = Post.get_by_id(post.id)
        assert post.updated_at > original_ts

    def test_touch_method(self, Post):
        post = Post.create(title="Hello")
        original_ts = post.updated_at

        sleep(0.01)
        post.touch()

        post = Post.get_by_id(post.id)
        assert post.updated_at > original_ts

    def test_touch_skips_none_relation(self, db, Post, RussianDollCached):
        """If the FK is null, touching is skipped gracefully."""
        class OptionalComment(RussianDollCached):
            post = pw.ForeignKeyField(Post, null=True, backref="opt_comments")
            body = pw.TextField()
            touches = ("post",)

            class Meta:
                table_name = "optional_comments"

        db.create_tables([OptionalComment])
        try:
            OptionalComment.create(post=None, body="orphan")
        finally:
            db.drop_tables([OptionalComment])
