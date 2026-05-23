"""Tests for proper.rich_text.concerns - HasRichText lifecycle mixin."""
from io import BytesIO

import peewee as pw
import pytest

from proper import App, current
from proper.models import ProperModel
from proper.rich_text import HasRichText, RichTextField


STORAGE_SERVICES = {"local": {"type": "Disk", "root": "temp/storage"}}


def _make_file(content=b"hello", filename="test.txt", content_type=""):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = content_type  # type: ignore
    return buf


@pytest.fixture()
def app(tmp_path):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        "STORAGE": "local",
        "STORAGE_SERVICES": STORAGE_SERVICES,
        "QUEUE": {
            "type": "huey.MemoryHuey",
            "immediate": True,
            "immediate_use_memory": True,
        },
    }
    app = App("tests", config)
    app.root_path = tmp_path / "app"
    app.root_path.mkdir(parents=True, exist_ok=True)
    current.app = app
    return app


@pytest.fixture()
def Attachment(app):
    return app.attachment_for(ProperModel)


@pytest.fixture()
def Post(app, Attachment):
    """A test model that uses HasRichText with one RichTextField column."""
    class _Post(HasRichText, ProperModel):
        body = RichTextField(null=True, attachment_cls=Attachment)

    database = pw.SqliteDatabase(":memory:")
    Attachment.bind(database)
    _Post.bind(database)
    database.create_tables([Attachment, _Post])
    yield _Post
    database.close()


@pytest.fixture()
def PostNoEmbeds(app):
    """A model with HasRichText but no embeds wired - lifecycle is a no-op."""
    class _Post(HasRichText, ProperModel):
        title = pw.CharField(default="")

    database = pw.SqliteDatabase(":memory:")
    _Post.bind(database)
    database.create_tables([_Post])
    yield _Post
    database.close()


@pytest.fixture()
def PostTwoBodies(app, Attachment):
    """A model with two RichTextField columns - both must be reconciled."""
    class _Post(HasRichText, ProperModel):
        body = RichTextField(null=True, attachment_cls=Attachment)
        summary = RichTextField(null=True, attachment_cls=Attachment)

    database = pw.SqliteDatabase(":memory:")
    Attachment.bind(database)
    _Post.bind(database)
    database.create_tables([Attachment, _Post])
    yield _Post
    database.close()


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


# ── new record with embeds ─────────────────────────────────────────


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


# ── update: removing/replacing embeds ──────────────────────────────


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


# ── delete ─────────────────────────────────────────────────────────


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


# ── multiple rich text columns ─────────────────────────────────────


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


# ── no rich text columns ───────────────────────────────────────────


def test_model_without_rich_text_fields_is_unaffected(PostNoEmbeds):
    """A model that mixes in HasRichText but has no RichTextField columns
    must still save and delete cleanly - the mixin is a no-op for it.
    """
    post = PostNoEmbeds(title="hello")
    post.save()
    refreshed = PostNoEmbeds.get(PostNoEmbeds.id == post.id)
    assert refreshed.title == "hello"
    refreshed.delete_instance()
    assert PostNoEmbeds.get_or_none(PostNoEmbeds.id == post.id) is None


# ── defensive: null body ───────────────────────────────────────────


def test_null_body_doesnt_crash(Post, Attachment):
    post = Post(body=None)
    post.save()
    post.body = None
    post.save()
    post.delete_instance()


# ── attachment_cls=None edge case ──────────────────────────────────


def test_field_without_attachment_cls_is_skipped(app):
    """A RichTextField with attachment_cls=None can't purge - the mixin
    must skip it without raising.
    """
    class _Post(HasRichText, ProperModel):
        body = RichTextField(null=True)  # no attachment_cls

    database = pw.SqliteDatabase(":memory:")
    _Post.bind(database)
    database.create_tables([_Post])

    try:
        post = _Post(body=_html_with_embed("ignored"))
        post.save()
        post.delete_instance()
    finally:
        database.close()


# ── internals: defensive walkers ───────────────────────────────────


def test_collect_ids_from_non_string_returns_empty():
    from proper.rich_text.concerns import _collect_attachment_ids
    assert _collect_attachment_ids(None) == []
    assert _collect_attachment_ids(123) == []


def test_collect_ids_from_html_without_attachments_returns_empty():
    from proper.rich_text.concerns import _collect_attachment_ids
    assert _collect_attachment_ids("<p>nothing here</p>") == []
