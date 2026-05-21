import peewee as pw
import pytest

from proper import App, current
from proper.models import ProperModel
from proper.rich_text import RichTextDocument, RichTextField


@pytest.fixture()
def app(tmp_path):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        "STORAGE": "local",
        "STORAGE_SERVICES": {"local": {"type": "Disk", "root": "temp/storage"}},
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
def Post(app):
    """Build a fresh test model on every test, bound to a fresh DB so
    state never leaks across tests.
    """
    class _Post(ProperModel):
        body = RichTextField(null=True)

    database = pw.SqliteDatabase(":memory:")
    _Post.bind(database)
    database.create_tables([_Post])
    yield _Post
    database.close()


@pytest.fixture()
def Attachment(app):
    return app.attachment_for(ProperModel)


@pytest.fixture()
def PostWithAttachments(app, Attachment):
    """Same as Post, but with attachment_cls wired so embeds resolve."""
    class _Post(ProperModel):
        body = RichTextField(Attachment, null=True)

    database = pw.SqliteDatabase(":memory:")
    Attachment.bind(database)
    _Post.bind(database)
    database.create_tables([Attachment, _Post])
    yield _Post
    database.close()


# ── round-tripping ──────────────────────────────────────────────────


def test_save_and_load_returns_document(Post):
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hi"}]},
        ],
    }
    Post.create(body=ast)
    post = Post.get()
    assert isinstance(post.body, RichTextDocument)
    assert post.body.to_dict() == ast


def test_can_assign_a_document(Post):
    doc = RichTextDocument({"type": "doc", "content": []})
    Post.create(body=doc)
    post = Post.get()
    assert post.body.to_dict() == {"type": "doc", "content": []}


def test_null_value_round_trips_as_none(Post):
    Post.create(body=None)
    post = Post.get()
    assert post.body is None


# ── attachment_cls propagates ───────────────────────────────────────


def test_attachment_cls_propagates_to_document(PostWithAttachments):
    PostWithAttachments.create(body={
        "type": "doc",
        "content": [{"type": "attachment", "attrs": {"id": "abc"}}],
    })
    post = PostWithAttachments.get()
    assert post.body._attachment_cls is not None
