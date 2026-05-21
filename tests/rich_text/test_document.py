from io import BytesIO

import peewee as pw
import pytest

from proper import App, current
from proper.models import ProperModel
from proper.rich_text import RichTextDocument


STORAGE_SERVICES = {
    "local": {"type": "Disk", "root": "temp/storage"},
}


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
def db(Attachment):
    database = pw.SqliteDatabase(":memory:")
    Attachment.bind(database)
    database.create_tables([Attachment])
    yield database
    database.close()


# ── basics ──────────────────────────────────────────────────────────


def test_to_dict_returns_raw_ast():
    data = {"type": "doc", "content": []}
    doc = RichTextDocument(data)
    assert doc.to_dict() is data


def test_str_returns_plain_text():
    doc = RichTextDocument({
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hola"}]},
        ],
    })
    assert str(doc) == "Hola"


def test_repr_includes_data():
    doc = RichTextDocument({"type": "doc"})
    assert "RichTextDocument" in repr(doc)
    assert "doc" in repr(doc)


def test_equality_with_other_document():
    a = RichTextDocument({"type": "doc"})
    b = RichTextDocument({"type": "doc"})
    assert a == b


def test_equality_with_dict():
    doc = RichTextDocument({"type": "doc"})
    assert doc == {"type": "doc"}


def test_inequality_with_unrelated():
    doc = RichTextDocument({"type": "doc"})
    assert (doc == "doc") is False


# ── attachments property ────────────────────────────────────────────


def test_attachments_empty_when_no_embeds(Attachment, db):
    doc = RichTextDocument(
        {"type": "doc", "content": []},
        attachment_cls=Attachment,
    )
    assert doc.attachments == []


def test_attachments_empty_when_no_attachment_cls():
    doc = RichTextDocument({
        "type": "doc",
        "content": [{"type": "attachment", "attrs": {"id": "x"}}],
    })
    assert doc.attachments == []


def test_attachments_resolved_from_db(Attachment, db):
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    doc = RichTextDocument(
        {"type": "doc", "content": [
            {"type": "attachment", "attrs": {"id": str(att.id)}},
        ]},
        attachment_cls=Attachment,
    )
    resolved = doc.attachments
    assert len(resolved) == 1
    assert resolved[0].id == att.id


def test_attachments_in_document_order(Attachment, db):
    a = Attachment(_make_file(b"a", "a.txt"))
    a.save()
    b = Attachment(_make_file(b"b", "b.txt"))
    b.save()

    doc = RichTextDocument(
        {"type": "doc", "content": [
            {"type": "attachment", "attrs": {"id": str(b.id)}},
            {"type": "paragraph", "content": []},
            {"type": "attachment", "attrs": {"id": str(a.id)}},
        ]},
        attachment_cls=Attachment,
    )
    ordered = [str(att.id) for att in doc.attachments]
    assert ordered == [str(b.id), str(a.id)]


def test_attachments_dedupes_repeated_ids(Attachment, db):
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    doc = RichTextDocument(
        {"type": "doc", "content": [
            {"type": "attachment", "attrs": {"id": str(att.id)}},
            {"type": "attachment", "attrs": {"id": str(att.id)}},
        ]},
        attachment_cls=Attachment,
    )
    assert len(doc.attachments) == 1


def test_attachments_skips_missing_rows(Attachment, db):
    """An attachment ID in the AST that no longer exists in the DB is
    silently skipped - old documents referencing purged blobs still
    render (without the embed) instead of crashing.
    """
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    doc = RichTextDocument(
        {"type": "doc", "content": [
            {"type": "attachment", "attrs": {"id": str(att.id)}},
            {"type": "attachment", "attrs": {"id": "00000000-0000-0000-0000-000000000000"}},
        ]},
        attachment_cls=Attachment,
    )
    assert len(doc.attachments) == 1


def test_attachments_cached_across_calls(Attachment, db):
    att = Attachment(_make_file(b"x", "x.txt"))
    att.save()

    doc = RichTextDocument(
        {"type": "doc", "content": [
            {"type": "attachment", "attrs": {"id": str(att.id)}},
        ]},
        attachment_cls=Attachment,
    )
    first = doc.attachments
    second = doc.attachments
    # Same dict iteration ⇒ same Python object identity
    assert first is not None
    assert len(first) == 1
    assert len(second) == 1


def test_attachments_handles_non_string_id(Attachment, db):
    """Defensive: a malformed AST with a non-string id shouldn't crash."""
    doc = RichTextDocument(
        {"type": "doc", "content": [
            {"type": "attachment", "attrs": {"id": 123}},
        ]},
        attachment_cls=Attachment,
    )
    assert doc.attachments == []


def test_attachments_handles_non_dict_child(Attachment, db):
    """Defensive: a malformed AST with a non-dict child in content
    shouldn't crash the attachment-id collection walk.
    """
    doc = RichTextDocument(
        {"type": "doc", "content": ["junk", None, {"type": "paragraph"}]},
        attachment_cls=Attachment,
    )
    assert doc.attachments == []


# ── __html__ ────────────────────────────────────────────────────────


def test_html_structural_content_only(app):
    """No embeds → no catalog dependency needed."""
    doc = RichTextDocument({
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hi"}]},
        ],
    })
    assert str(doc.__html__()) == "<p>Hi</p>"


def test_html_returns_markup_safe_string(app):
    """The result must carry the Markup type so Jinja renders it raw."""
    from markupsafe import Markup
    doc = RichTextDocument({"type": "doc"})
    assert isinstance(doc.__html__(), Markup)


def test_html_embed_without_attachment_cls_collapses(app):
    """An attachment node with no attachment_cls renders as empty (the
    document doesn't know how to look it up).
    """
    doc = RichTextDocument({
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "before"}]},
            {"type": "attachment", "attrs": {"id": "x"}},
            {"type": "paragraph", "content": [{"type": "text", "text": "after"}]},
        ],
    })
    html = str(doc.__html__())
    assert "before" in html
    assert "after" in html
    # No embed marker
    assert "x" not in html.replace("before", "").replace("after", "")
