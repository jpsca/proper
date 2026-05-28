from io import BytesIO

import peewee as pw

from proper.rich_text import HasRichText


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
    """Create a rich-text-source attachment and return it (pending=True)."""
    att = Attachment(
        _make_file(content, filename),
        source="rich_text",
        pending=True,
    )
    att.save()
    return att


# --- New record with embeds ---


def test_new_post_with_embed_flips_pending_to_false(Post, Attachment):
    att = _store_attachment(Attachment)
    assert att.pending is True

    post = Post(body=_html_with_embed(str(att.id)))
    post.save()

    refreshed = Attachment.get(Attachment.id == att.id)
    assert refreshed.pending is False


def test_new_post_without_embeds_does_nothing(Post, Attachment):
    other = _store_attachment(Attachment)
    post = Post(body=_empty_html())
    post.save()

    # Unrelated pending attachment is untouched.
    refreshed = Attachment.get(Attachment.id == other.id)
    assert refreshed.pending is True


# --- Update: removing/replacing embeds ---


def test_edit_removing_embed_purges_it(Post, Attachment):
    keep = _store_attachment(Attachment, b"a", "a.txt")
    drop = _store_attachment(Attachment, b"b", "b.txt")

    post = Post(body=_html_with_embeds(str(keep.id), str(drop.id)))
    post.save()

    # Both flipped to pending=False on first save
    assert Attachment.get(Attachment.id == keep.id).pending is False
    assert Attachment.get(Attachment.id == drop.id).pending is False

    # Now edit the post, removing the `drop` embed
    post.body = _html_with_embed(str(keep.id))
    post.save()

    # `drop` is purged; `keep` remains
    assert Attachment.get_or_none(Attachment.id == drop.id) is None
    assert Attachment.get_or_none(Attachment.id == keep.id) is not None


def test_edit_adding_embed_flips_only_new_one(Post, Attachment):
    first = _store_attachment(Attachment, b"a", "a.txt")
    post = Post(body=_html_with_embed(str(first.id)))
    post.save()

    second = _store_attachment(Attachment, b"b", "b.txt")
    assert second.pending is True

    post.body = _html_with_embeds(str(first.id), str(second.id))
    post.save()

    assert Attachment.get(Attachment.id == second.id).pending is False
    assert Attachment.get_or_none(Attachment.id == first.id) is not None


def test_edit_replacing_one_embed_with_another_purges_removed(Post, Attachment):
    old = _store_attachment(Attachment, b"a", "a.txt")
    new = _store_attachment(Attachment, b"b", "b.txt")

    post = Post(body=_html_with_embed(str(old.id)))
    post.save()

    post.body = _html_with_embed(str(new.id))
    post.save()

    assert Attachment.get_or_none(Attachment.id == old.id) is None
    assert Attachment.get(Attachment.id == new.id).pending is False


# --- Delete ---


def test_delete_purges_all_embedded_attachments(Post, Attachment):
    a = _store_attachment(Attachment, b"a", "a.txt")
    b = _store_attachment(Attachment, b"b", "b.txt")
    post = Post(body=_html_with_embeds(str(a.id), str(b.id)))
    post.save()

    post.delete_instance()

    assert Attachment.get_or_none(Attachment.id == a.id) is None
    assert Attachment.get_or_none(Attachment.id == b.id) is None


def test_delete_with_no_embeds_is_a_noop(Post, Attachment):
    other = _store_attachment(Attachment)
    post = Post(body=_empty_html())
    post.save()

    post.delete_instance()

    # Unrelated attachment is unaffected
    assert Attachment.get_or_none(Attachment.id == other.id) is not None


# --- Multiple rich text columns ---


def test_multiple_rich_text_fields_are_all_reconciled(PostTwoBodies, Attachment):
    main = _store_attachment(Attachment, b"main", "main.txt")
    side = _store_attachment(Attachment, b"side", "side.txt")

    post = PostTwoBodies(
        body=_html_with_embed(str(main.id)),
        summary=_html_with_embed(str(side.id)),
    )
    post.save()

    # Both columns' embeds confirmed
    assert Attachment.get(Attachment.id == main.id).pending is False
    assert Attachment.get(Attachment.id == side.id).pending is False

    # Remove the summary embed only
    post.summary = _empty_html()
    post.save()

    # Summary's embed purged, body's intact
    assert Attachment.get_or_none(Attachment.id == side.id) is None
    assert Attachment.get_or_none(Attachment.id == main.id) is not None


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
    post.delete_instance()


def test_collect_ids_from_non_string_returns_empty():
    from proper.rich_text.concerns import _collect_attachment_ids
    assert _collect_attachment_ids(None) == []
    assert _collect_attachment_ids(123) == []


def test_collect_ids_from_html_without_attachments_returns_empty():
    from proper.rich_text.concerns import _collect_attachment_ids
    assert _collect_attachment_ids("<p>nothing here</p>") == []
