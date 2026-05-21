"""Tests for proper.rich_text.tasks - abandoned-upload sweep."""
from datetime import timedelta
from io import BytesIO

import peewee as pw
import pytest

from proper import App, current
from proper.models import ProperModel
from proper.rich_text import purge_abandoned_uploads


STORAGE_SERVICES = {"local": {"type": "Disk", "root": "temp/storage"}}


def _make_file(content=b"x", filename="x.txt"):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = ""  # type: ignore
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


def _make_attachment(Attachment, *, source, pending, age_hours, content=b"x"):
    """Create an attachment with overridden source/pending/age."""
    # Use unique filenames so concurrent tests don't collide on disk.
    import uuid
    name = f"{uuid.uuid4().hex}.txt"
    att = Attachment(_make_file(content, name), source=source, pending=pending)
    att.save()
    if age_hours:
        Attachment.update(
            created_at=pw.utcnow() - timedelta(hours=age_hours)
        ).where(Attachment.id == att.id).execute()
    return att


# ── filter behavior ─────────────────────────────────────────────────


def test_purges_rich_text_pending_past_cutoff(Attachment, db):
    abandoned = _make_attachment(
        Attachment, source="rich_text", pending=True, age_hours=25,
    )
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 1
    assert Attachment.get_or_none(Attachment.id == abandoned.id) is None


def test_keeps_rich_text_pending_within_grace(Attachment, db):
    recent = _make_attachment(
        Attachment, source="rich_text", pending=True, age_hours=1,
    )
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 0
    assert Attachment.get_or_none(Attachment.id == recent.id) is not None


def test_keeps_direct_source_even_when_old_and_pending(Attachment, db):
    """`source="direct"` uploads aren't part of the editor lifecycle and
    must never be touched by this sweep, no matter how old.
    """
    direct = _make_attachment(
        Attachment, source="direct", pending=True, age_hours=999,
    )
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 0
    assert Attachment.get_or_none(Attachment.id == direct.id) is not None


def test_keeps_rich_text_already_confirmed(Attachment, db):
    """A rich-text attachment whose parent has confirmed it (pending=False)
    is owned by something and must not be swept, even if old.
    """
    confirmed = _make_attachment(
        Attachment, source="rich_text", pending=False, age_hours=999,
    )
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 0
    assert Attachment.get_or_none(Attachment.id == confirmed.id) is not None


def test_purges_multiple_orphans_in_one_pass(Attachment, db):
    abandoned = [
        _make_attachment(
            Attachment, source="rich_text", pending=True, age_hours=48,
        )
        for _ in range(3)
    ]
    count = purge_abandoned_uploads(Attachment, grace_hours=24)
    assert count == 3
    for att in abandoned:
        assert Attachment.get_or_none(Attachment.id == att.id) is None


def test_grace_hours_default_is_24(Attachment, db):
    """The default grace period is 24h - calling with no arg uses it."""
    at_23 = _make_attachment(
        Attachment, source="rich_text", pending=True, age_hours=23,
    )
    at_25 = _make_attachment(
        Attachment, source="rich_text", pending=True, age_hours=25,
    )
    count = purge_abandoned_uploads(Attachment)  # default grace_hours=24
    assert count == 1
    assert Attachment.get_or_none(Attachment.id == at_23.id) is not None
    assert Attachment.get_or_none(Attachment.id == at_25.id) is None


def test_grace_hours_zero_purges_all_pending(Attachment, db):
    """``grace_hours=0`` is the "force sweep" mode useful for tests
    and for manual triggers when an admin wants immediate cleanup.
    """
    a = _make_attachment(
        Attachment, source="rich_text", pending=True, age_hours=0,
    )
    count = purge_abandoned_uploads(Attachment, grace_hours=0)
    assert count == 1
    assert Attachment.get_or_none(Attachment.id == a.id) is None
