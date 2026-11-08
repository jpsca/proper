from io import BytesIO

import peewee as pw
import pytest

from proper.rich_text import HasRichText, rebuild_rich_text_references
from proper.rich_text.concerns import _collect_attachment_ids


def _make_file(content=b"hello", filename="test.txt", content_type=""):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = content_type  # type: ignore
    return buf

def _html_with_embed(att_id: str) -> str:
    return f'<proper-attachment sgid="{att_id}"></proper-attachment>'


def _html_with_embeds(*ids: str) -> str:
    return "".join(_html_with_embed(x) for x in ids)


def _empty_html() -> str:
    return ""


def _store_attachment(Attachment, content=b"x", filename="x.txt"):
    """Create an attachment as the rich text editor does, and return it."""
    att = Attachment(_make_file(content, filename), source="rich_text")
    att.save()
    return att


def _references(Attachment, record=None):
    """`{(record_type, record_id, field, attachment_id), ...}`, of one
    record or of all of them."""
    Reference = Attachment.Reference
    query = Reference.select()
    if record is not None:
        query = query.where(
            (Reference.record_type == type(record)._meta.table_name)
            & (Reference.record_id == str(record.id))
        )
    return {
        (row.record_type, row.record_id, row.field, row.attachment_id)
        for row in query
    }


def _exists(Attachment, att) -> bool:
    return Attachment.get_or_none(Attachment.id == att.id) is not None


# --- New record with embeds ---


def test_new_post_with_embed_adds_a_reference(Post, Attachment):
    att = _store_attachment(Attachment)
    assert not att.is_referenced

    post = Post(body=_html_with_embed(str(att.id)))
    post.save()

    assert att.is_referenced
    assert _references(Attachment) == {("post", str(post.id), "body", att.id)}


def test_new_post_without_embeds_does_nothing(Post, Attachment):
    other = _store_attachment(Attachment)
    post = Post(body=_empty_html())
    post.save()

    assert _references(Attachment) == set()
    assert not other.is_referenced
    assert _exists(Attachment, other)


def test_saving_twice_doesnt_duplicate_references(Post, Attachment):
    att = _store_attachment(Attachment)
    post = Post(body=_html_with_embed(str(att.id)))
    post.save()
    post.save()

    assert Attachment.Reference.select().count() == 1


def test_embed_of_an_unknown_attachment_gets_no_reference(Post, Attachment):
    post = Post(body=_html_with_embed("no-such-attachment"))
    post.save()

    assert _references(Attachment) == set()


def test_same_embed_twice_in_a_body_is_one_reference(Post, Attachment):
    att = _store_attachment(Attachment)
    post = Post(body=_html_with_embeds(str(att.id), str(att.id)))
    post.save()

    assert Attachment.Reference.select().count() == 1


# --- Update: removing/replacing embeds ---


def test_edit_removing_embed_purges_it(Post, Attachment):
    keep = _store_attachment(Attachment, b"a", "a.txt")
    drop = _store_attachment(Attachment, b"b", "b.txt")

    post = Post(body=_html_with_embeds(str(keep.id), str(drop.id)))
    post.save()
    assert keep.is_referenced
    assert drop.is_referenced

    post.body = _html_with_embed(str(keep.id))
    post.save()

    assert not _exists(Attachment, drop)
    assert _exists(Attachment, keep)
    assert _references(Attachment) == {("post", str(post.id), "body", keep.id)}


def test_edit_adding_embed_references_only_new_one(Post, Attachment):
    first = _store_attachment(Attachment, b"a", "a.txt")
    post = Post(body=_html_with_embed(str(first.id)))
    post.save()

    second = _store_attachment(Attachment, b"b", "b.txt")
    assert not second.is_referenced

    post.body = _html_with_embeds(str(first.id), str(second.id))
    post.save()

    assert second.is_referenced
    assert _exists(Attachment, first)
    assert len(_references(Attachment, post)) == 2


def test_edit_replacing_one_embed_with_another_purges_removed(Post, Attachment):
    old = _store_attachment(Attachment, b"a", "a.txt")
    new = _store_attachment(Attachment, b"b", "b.txt")

    post = Post(body=_html_with_embed(str(old.id)))
    post.save()

    post.body = _html_with_embed(str(new.id))
    post.save()

    assert not _exists(Attachment, old)
    assert new.is_referenced


def test_edit_removing_an_embed_another_record_keeps_doesnt_purge_it(
    Post, Attachment
):
    shared = _store_attachment(Attachment)
    first = Post(body=_html_with_embed(str(shared.id)))
    first.save()
    second = Post(body=_html_with_embed(str(shared.id)))
    second.save()

    first.body = _empty_html()
    first.save()

    assert _exists(Attachment, shared)
    assert _references(Attachment) == {("post", str(second.id), "body", shared.id)}


# --- Delete ---


def test_delete_purges_all_embedded_attachments(Post, Attachment):
    a = _store_attachment(Attachment, b"a", "a.txt")
    b = _store_attachment(Attachment, b"b", "b.txt")
    post = Post(body=_html_with_embeds(str(a.id), str(b.id)))
    post.save()

    post.delete_instance()

    assert not _exists(Attachment, a)
    assert not _exists(Attachment, b)
    assert _references(Attachment) == set()


def test_delete_with_no_embeds_is_a_noop(Post, Attachment):
    other = _store_attachment(Attachment)
    post = Post(body=_empty_html())
    post.save()

    post.delete_instance()

    assert _exists(Attachment, other)


def test_delete_keeps_an_attachment_another_record_embeds(Post, Attachment):
    shared = _store_attachment(Attachment)
    first = Post(body=_html_with_embed(str(shared.id)))
    first.save()
    second = Post(body=_html_with_embed(str(shared.id)))
    second.save()

    first.delete_instance()
    assert _exists(Attachment, shared)
    assert _references(Attachment) == {("post", str(second.id), "body", shared.id)}

    second.delete_instance()
    assert not _exists(Attachment, shared)
    assert _references(Attachment) == set()


def test_a_copy_of_a_record_keeps_its_attachments(Post, Attachment):
    """The case of versioned records: every version is a new row with
    the same body. Deleting the original keeps the files of the copy."""
    att = _store_attachment(Attachment)
    original = Post(body=_html_with_embed(str(att.id)))
    original.save()
    copy = Post(body=original.body)
    copy.save()

    original.delete_instance()

    assert _exists(Attachment, att)
    copy = Post.get(Post.id == copy.id)
    assert [a.id for a in copy.body.attachments] == [att.id]


# --- release_rich_text_attachments ---


def test_release_then_delete_by_query_equals_delete_instance(Post, Attachment):
    own = _store_attachment(Attachment, b"a", "a.txt")
    shared = _store_attachment(Attachment, b"b", "b.txt")
    post = Post(body=_html_with_embeds(str(own.id), str(shared.id)))
    post.save()
    other = Post(body=_html_with_embed(str(shared.id)))
    other.save()

    post.release_rich_text_attachments()
    Post.delete().where(Post.id == post.id).execute()

    assert not _exists(Attachment, own)
    assert _exists(Attachment, shared)
    assert _references(Attachment) == {("post", str(other.id), "body", shared.id)}


def test_release_without_references_is_a_noop(Post, Attachment):
    other = _store_attachment(Attachment)
    post = Post(body=_empty_html())
    post.save()

    post.release_rich_text_attachments()

    assert _exists(Attachment, other)


# --- Multiple rich text columns ---


def test_multiple_rich_text_fields_are_all_reconciled(PostTwoBodies, Attachment):
    main = _store_attachment(Attachment, b"main", "main.txt")
    side = _store_attachment(Attachment, b"side", "side.txt")

    post = PostTwoBodies(
        body=_html_with_embed(str(main.id)),
        summary=_html_with_embed(str(side.id)),
    )
    post.save()

    assert _references(Attachment) == {
        ("posttwobodies", str(post.id), "body", main.id),
        ("posttwobodies", str(post.id), "summary", side.id),
    }

    # Remove the summary embed only
    post.summary = _empty_html()
    post.save()

    assert not _exists(Attachment, side)
    assert _exists(Attachment, main)


def test_same_embed_in_two_fields_is_purged_when_both_drop_it(
    PostTwoBodies, Attachment
):
    att = _store_attachment(Attachment)
    post = PostTwoBodies(
        body=_html_with_embed(str(att.id)),
        summary=_html_with_embed(str(att.id)),
    )
    post.save()
    assert len(_references(Attachment, post)) == 2

    post.summary = _empty_html()
    post.save()
    assert _exists(Attachment, att)
    assert _references(Attachment) == {("posttwobodies", str(post.id), "body", att.id)}

    post.body = _empty_html()
    post.save()
    assert not _exists(Attachment, att)


def test_delete_with_two_fields_removes_every_reference(PostTwoBodies, Attachment):
    att = _store_attachment(Attachment)
    post = PostTwoBodies(
        body=_html_with_embed(str(att.id)),
        summary=_html_with_embed(str(att.id)),
    )
    post.save()

    post.delete_instance()

    assert not _exists(Attachment, att)
    assert _references(Attachment) == set()


# --- rebuild_rich_text_references ---


def test_rebuild_fills_the_references_of_existing_rows(Post, Attachment):
    """Rows saved before the references existed: insert the HTML with a
    query so `HasRichText` doesn't see it."""
    a = _store_attachment(Attachment, b"a", "a.txt")
    b = _store_attachment(Attachment, b"b", "b.txt")
    Post.insert(body=_html_with_embeds(str(a.id), str(b.id))).execute()
    Post.insert(body=_html_with_embed(str(b.id))).execute()
    first, second = list(Post.select().order_by(Post.id))
    assert _references(Attachment) == set()

    rebuild_rich_text_references(Post)

    assert _references(Attachment) == {
        ("post", str(first.id), "body", a.id),
        ("post", str(first.id), "body", b.id),
        ("post", str(second.id), "body", b.id),
    }


def test_rebuild_removes_the_references_of_deleted_rows(Post, Attachment):
    att = _store_attachment(Attachment)
    post = Post(body=_html_with_embed(str(att.id)))
    post.save()
    kept = Post(body=_html_with_embed(str(att.id)))
    kept.save()
    Post.delete().where(Post.id == post.id).execute()
    assert len(_references(Attachment)) == 2

    rebuild_rich_text_references(Post)

    assert _references(Attachment) == {("post", str(kept.id), "body", att.id)}
    # Nothing is purged by the rebuild.
    assert _exists(Attachment, att)


def test_rebuild_syncs_a_body_changed_by_a_query(Post, Attachment):
    old = _store_attachment(Attachment, b"a", "a.txt")
    new = _store_attachment(Attachment, b"b", "b.txt")
    post = Post(body=_html_with_embed(str(old.id)))
    post.save()
    Post.update(body=_html_with_embed(str(new.id))).where(Post.id == post.id).execute()

    rebuild_rich_text_references(Post)

    assert _references(Attachment) == {("post", str(post.id), "body", new.id)}
    assert _exists(Attachment, old)


def test_rebuild_takes_several_models(Post, PostTwoBodies, Attachment):
    att = _store_attachment(Attachment)
    Post.insert(body=_html_with_embed(str(att.id))).execute()
    PostTwoBodies.insert(summary=_html_with_embed(str(att.id))).execute()

    rebuild_rich_text_references(Post, PostTwoBodies)

    assert {row[0] for row in _references(Attachment)} == {"post", "posttwobodies"}


def test_rebuild_of_a_model_without_attachments_does_nothing(PostNoAttachments):
    PostNoAttachments.insert(body=_html_with_embed("ignored")).execute()
    rebuild_rich_text_references(PostNoAttachments)


# --- Defensive ---


def test_model_without_rich_text_fields_is_unaffected(db, BaseModel):
    """A model that mixes in HasRichText but has no RichTextField columns
    must still save and delete cleanly - the mixin is a no-op for it.
    """
    class PostNoEmbeds(HasRichText, BaseModel):
        title = pw.CharField(default="")

    PostNoEmbeds.bind(db)
    db.create_tables([PostNoEmbeds])

    post = PostNoEmbeds(title="hello")
    post.save()
    refreshed = PostNoEmbeds.get(PostNoEmbeds.id == post.id)
    assert refreshed.title == "hello"
    refreshed.delete_instance()
    assert PostNoEmbeds.get_or_none(PostNoEmbeds.id == post.id) is None


def test_null_body_doesnt_crash(Post):
    post = Post(body=None)
    post.save()
    post.body = None
    post.save()
    post.delete_instance()


def test_field_without_attachment_cls_is_skipped(PostNoAttachments):
    """A RichTextField with attachment_cls=None can't purge - the mixin
    must skip it without raising.
    """
    post = PostNoAttachments(body=_html_with_embed("ignored"))
    post.save()
    post.release_rich_text_attachments()
    post.delete_instance()


def test_collect_ids_from_non_string_returns_empty():
    assert _collect_attachment_ids(None) == []
    assert _collect_attachment_ids(123) == []


def test_collect_ids_from_html_without_attachments_returns_empty():
    assert _collect_attachment_ids("<p>nothing here</p>") == []


# --- Base order guard ---


def test_mixin_after_the_model_class_is_rejected(db):
    """Peewee's `Model.save()` doesn't call `super()`: a mixin listed after
    the model would silently never run, so it must fail loudly instead.
    """
    class BaseModel(pw.Model):
        class Meta:
            database = db

    with pytest.raises(TypeError, match=r"HasRichText.*before the model class"):
        class Post(BaseModel, HasRichText):  # noqa: F841
            body = pw.TextField(null=True)


def test_mixin_before_the_model_class_is_accepted(db):
    class BaseModel(pw.Model):
        class Meta:
            database = db

    class Post(HasRichText, BaseModel):
        body = pw.TextField(null=True)

    # The hooks are reachable: the mixin's `save` is the one that runs.
    assert Post.save is HasRichText.save
    assert Post.delete_instance is HasRichText.delete_instance


def test_intermediate_mixins_are_not_checked_until_they_meet_a_model(db):
    class Auditable(HasRichText):
        """A plain mixin building on HasRichText: no model in sight yet."""

    class BaseModel(pw.Model):
        class Meta:
            database = db

    class Good(Auditable, BaseModel):
        pass

    assert Good.save is HasRichText.save

    with pytest.raises(TypeError, match="Bad"):
        class Bad(BaseModel, Auditable):  # noqa: F841
            pass
