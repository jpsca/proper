import peewee as pw
import pytest

from proper import App, current
from proper.models import ProperModel
from proper.rich_text import HasRichText, RichTextField


STORAGE_SERVICES = {"local": {"type": "Disk", "root": "temp/storage"}}


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
    app = App(__name__, config)
    app.root_path = tmp_path / "app"
    app.root_path.mkdir(parents=True, exist_ok=True)
    current.app = app
    return app


@pytest.fixture()
def db():
    database = pw.SqliteDatabase(":memory:")
    yield database
    database.close()


@pytest.fixture()
def BaseModel(db):
    class BaseModel(ProperModel):
        """Stand-in for the consumer's BaseModel. Real apps subclass ProperModel
        once and reuse that as the storage base; `attachment_for` requires a
        distinct subclass (not ProperModel itself) so the MRO can place the
        consumer base before `_Attachment` without conflict.
        """

        class Meta:
            database = db

    return BaseModel


@pytest.fixture()
def Attachment(app, db, BaseModel):
    # Mutate `VARIANTS_ENABLED_FOR` on the returned class rather than
    # subclassing: `@queue.task` captures the decorated class eagerly,
    # so further subclassing strands Huey task dispatch on the parent.
    Attachment = app.attachment_for(BaseModel)
    Attachment.VARIANTS_ENABLED_FOR = {"image/*": "preview_image"}
    Attachment.bind(db)
    db.create_tables([Attachment])
    return Attachment


@pytest.fixture()
def Post(db, BaseModel, Attachment):
    class Post(HasRichText, BaseModel):
        body = RichTextField(null=True, attachment_cls=Attachment)

    Post.bind(db)
    db.create_tables([Post])
    return Post


@pytest.fixture()
def PostNoAttachments(db, BaseModel):
    class PostNoAttachments(HasRichText, BaseModel):
        body = RichTextField(None, null=True)

    PostNoAttachments.bind(db)
    db.create_tables([PostNoAttachments])
    return PostNoAttachments


@pytest.fixture()
def PostTwoBodies(db, BaseModel, Attachment):
    class PostTwoBodies(HasRichText, BaseModel):
        body = RichTextField(null=True, attachment_cls=Attachment)
        summary = RichTextField(null=True, attachment_cls=Attachment)

    PostTwoBodies.bind(db)
    db.create_tables([PostTwoBodies])
    return PostTwoBodies
