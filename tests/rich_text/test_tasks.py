import uuid
from datetime import timedelta
from io import BytesIO

import peewee as pw

from proper.rich_text import purge_abandoned_uploads


def _make_file(content=b"x", filename="x.txt"):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = ""  # type: ignore
    return buf


def _make_attachment(Attachment, *, source="rich_text", age_hours=0, content=b"x"):
    """Create an attachment with overridden source and age."""
    # Use unique filenames so concurrent tests don't collide on disk.
    name = f"{uuid.uuid4().hex}.txt"
    att = Attachment(_make_file(content, name), source=source)
    att.save()
    if age_hours:
        Attachment.update(
            created_at=pw.utcnow() - timedelta(hours=age_hours)
        ).where(Attachment.id == att.id).execute()
    return att


def _embed(Post, att):
    post = Post(body=f'<proper-attachment sgid="{att.id}"></proper-attachment>')
    post.save()
    return post


def _exists(Attachment, att) -> bool:
    return Attachment.get_or_none(Attachment.id == att.id) is not None


# --- filter behavior ---


def test_purges_unreferenced_rich_text_uploads_past_cutoff(Attachment, db):
    """DirectUpload creates blobs with `source="rich_text"`. If no record
    embeds them within the grace period, the sweep purges them."""
    abandoned = _make_attachment(Attachment, age_hours=25)
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 1
    assert not _exists(Attachment, abandoned)


def test_keeps_unreferenced_within_grace(Attachment, db):
    recent = _make_attachment(Attachment, age_hours=1)
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 0
    assert _exists(Attachment, recent)


def test_keeps_other_sources_even_when_old_and_unreferenced(Attachment, db):
    """A file sent with a form or attached through a foreign key has an
    empty `source` and no references, and is in use. Never swept."""
    other = _make_attachment(Attachment, source="", age_hours=999)
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 0
    assert _exists(Attachment, other)


def test_keeps_referenced(Post, Attachment, db):
    """An upload that a record embeds is owned by it and must not be
    swept, even if old."""
    embedded = _make_attachment(Attachment, age_hours=999)
    _embed(Post, embedded)
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 0
    assert _exists(Attachment, embedded)


def test_keeps_variants(Attachment, db):
    """A variant has no references of its own: it goes with its parent."""
    parent = _make_attachment(Attachment, age_hours=999)
    variant = parent.create_variant(_make_file(b"v", "v.txt"), source="rich_text")
    Attachment.update(created_at=pw.utcnow() - timedelta(hours=999)).where(
        Attachment.id == variant.id
    ).execute()

    count = purge_abandoned_uploads(Attachment, grace_hours=24)

    # The parent is swept, and takes its variant with it.
    assert count == 1
    assert not _exists(Attachment, parent)
    assert not _exists(Attachment, variant)


def test_purges_multiple_orphans_in_one_pass(Attachment, db):
    abandoned = [_make_attachment(Attachment, age_hours=48) for _ in range(3)]
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 3
    for att in abandoned:
        assert not _exists(Attachment, att)


def test_grace_hours_default_is_24(Attachment, db):
    """The default grace period is 24h - calling with no arg uses it."""
    at_23 = _make_attachment(Attachment, age_hours=23)
    at_25 = _make_attachment(Attachment, age_hours=25)
    count = purge_abandoned_uploads(Attachment)  # default grace_hours=24
    assert count == 1
    assert _exists(Attachment, at_23)
    assert not _exists(Attachment, at_25)


def test_grace_hours_zero_purges_all_unreferenced(Attachment, db):
    """``grace_hours=0`` is the "force sweep" mode useful for tests
    and for manual triggers when an admin wants immediate cleanup.
    """
    a = _make_attachment(Attachment, age_hours=0)
    count = purge_abandoned_uploads(Attachment, grace_hours=0)
    assert count == 1
    assert not _exists(Attachment, a)


def test_source_arg_targets_a_specific_tag(Attachment, db):
    """Apps that tag uploads with their own `source` can pass `source=`
    to sweep them."""
    own = _make_attachment(Attachment, source="comments", age_hours=48)
    rich_text = _make_attachment(Attachment, age_hours=48)
    count = purge_abandoned_uploads(Attachment, grace_hours=24, source="comments")
    assert count == 1
    assert not _exists(Attachment, own)
    assert _exists(Attachment, rich_text)
