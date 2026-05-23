"""Integration tests for proper.storage.services.S3 against a MinIO container."""

from io import BytesIO

import peewee as pw
import pytest

from proper import App
from proper.models import ProperModel
from proper.storage.services import S3


MINIO_ROOT_USER = "minioadmin"
MINIO_ROOT_PASSWORD = "minioadmin"
MINIO_BUCKET = "test-bucket"


# ── helpers ─────────────────────────────────────────────────────────


def _make_file(content=b"hello", filename="test.txt", content_type=""):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = content_type  # type: ignore
    return buf


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def app(tmp_path, minio):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        "STORAGE": "s3",
        "STORAGE_SERVICES": {
            "s3": {
                "type": "S3",
                "bucket": MINIO_BUCKET,
                "endpoint": minio,
                "access_key_id": MINIO_ROOT_USER,
                "secret_access_key": MINIO_ROOT_PASSWORD,
            },
        },
    }
    app = App("tests", config)
    app.root_path = tmp_path / "app"
    app.root_path.mkdir(parents=True, exist_ok=True)
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


# ═══════════════════════════════════════════════════════════════════
# S3 service - basic operations
# ═══════════════════════════════════════════════════════════════════


def test_service_is_s3(Attachment):
    service = Attachment._get_service("s3")
    assert isinstance(service, S3)


def test_upload_and_download(Attachment, db):
    att = Attachment(_make_file(b"hello s3", "s3test.txt"))
    att.save(force_insert=True)
    assert att.download() == b"hello s3"


def test_upload_sets_byte_size(Attachment, db):
    att = Attachment(_make_file(b"12345", "f.txt"))
    att.save(force_insert=True)
    assert att.byte_size == 5


def test_upload_content_type(app, Attachment, db):
    att = Attachment(
        _make_file(b"img-data", "photo.jpg"),
        content_type="image/jpeg",
    )
    att.save(force_insert=True)
    service = Attachment._get_service("s3")
    resp = service.client.head_object(
        Bucket=MINIO_BUCKET,
        Key=service._get_key(att),
    )
    assert resp["ContentType"] == "image/jpeg"


def test_upload_handles_closed_file(app, Attachment, db):
    f = _make_file(b"some data", "f.txt")
    att = Attachment(f)
    att.save(force_insert=True)  # should not raise even if boto3 closes the stream


def test_download_different_files(Attachment, db):
    att1 = Attachment(_make_file(b"aaa", "a.txt"))
    att1.save(force_insert=True)
    att2 = Attachment(_make_file(b"bbb", "b.txt"))
    att2.save(force_insert=True)
    assert att1.download() == b"aaa"
    assert att2.download() == b"bbb"


# ═══════════════════════════════════════════════════════════════════
# S3 service - key sharding
# ═══════════════════════════════════════════════════════════════════


def test_key_uses_id_sharding(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    service = Attachment._get_service("s3")
    key = service._get_key(att)
    att_id = str(att.id)
    assert key.startswith(f"{att_id[:2]}/{att_id[2:4]}/")


# ═══════════════════════════════════════════════════════════════════
# S3 service - purge
# ═══════════════════════════════════════════════════════════════════


def test_purge_deletes_object(app, Attachment, db):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    service = Attachment._get_service("s3")
    key = service._get_key(att)

    # Verify it exists
    service.client.head_object(Bucket=MINIO_BUCKET, Key=key)

    att.purge()

    # Verify it's gone
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        service.client.head_object(Bucket=MINIO_BUCKET, Key=key)


def test_purge_deletes_record(Attachment, db):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    assert Attachment.select().count() == 1
    att.purge()
    assert Attachment.select().count() == 0


# ═══════════════════════════════════════════════════════════════════
# S3 service - send_file
# ═══════════════════════════════════════════════════════════════════


def test_send_file_inline(app, Attachment, db):
    att = Attachment(
        _make_file(b"contents", "report.pdf"),
        content_type="application/pdf",
    )
    att.save(force_insert=True)

    class FakeResponse:
        content_type = None
        body = None
        headers = {}

        def set_content_length(self, length):
            self.content_length = length

    resp = FakeResponse()
    service = Attachment._get_service("s3")
    service.send_file(att, resp, as_attachment=False)

    assert resp.body == b"contents"
    assert resp.content_type == "application/pdf"
    assert resp.content_length == 8
    assert resp.headers["content-disposition"] == 'inline; filename="report.pdf"'


def test_send_file_as_attachment(app, Attachment, db):
    att = Attachment(_make_file(b"data", "f.txt"), content_type="text/plain")
    att.save(force_insert=True)

    class FakeResponse:
        content_type = None
        body = None
        headers = {}

        def set_content_length(self, length):
            self.content_length = length

    resp = FakeResponse()
    service = Attachment._get_service("s3")
    service.send_file(att, resp, as_attachment=True)

    assert resp.headers["content-disposition"] == 'attachment; filename="f.txt"'


# ═══════════════════════════════════════════════════════════════════
# S3 service - round-trip through Attachment model
# ═══════════════════════════════════════════════════════════════════


def test_fields_survive_round_trip(Attachment, db):
    att = Attachment(
        _make_file(b"data", "photo.jpg"),
        content_type="image/jpeg",
    )
    att.save(force_insert=True)
    loaded = Attachment.get_or_none(Attachment.id == att.id)
    assert loaded.service_name == "s3"
    assert loaded.filename == "photo.jpg"
    assert loaded.content_type == "image/jpeg"
    assert loaded.byte_size == 4


def test_download_after_reload(Attachment, db):
    att = Attachment(_make_file(b"round trip", "f.txt"))
    att.save(force_insert=True)
    loaded = Attachment.get_or_none(Attachment.id == att.id)
    assert loaded.download() == b"round trip"


# ═══════════════════════════════════════════════════════════════════
# S3.service_url — presigned URLs
# ═══════════════════════════════════════════════════════════════════


def test_service_url_returns_signed_url(app, Attachment, db):
    att = Attachment(
        _make_file(b"hi", "shot.png"),
        content_type="image/png",
    )
    att.save(force_insert=True)

    url = Attachment._get_service("s3").service_url(att)

    assert url.startswith("http")
    # Standard SigV4 query params
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=" in url


def test_service_url_inline_by_default(app, Attachment, db):
    from urllib.request import urlopen

    att = Attachment(
        _make_file(b"bytes", "report.pdf"),
        content_type="application/pdf",
    )
    att.save(force_insert=True)

    url = Attachment._get_service("s3").service_url(att)
    with urlopen(url, timeout=5) as resp:
        body = resp.read()
        headers = dict(resp.headers)

    assert body == b"bytes"
    assert headers["Content-Type"] == "application/pdf"
    assert headers["Content-Disposition"] == 'inline; filename="report.pdf"'


def test_service_url_as_attachment_sets_download_disposition(app, Attachment, db):
    from urllib.request import urlopen

    att = Attachment(_make_file(b"x", "data.bin"), content_type="application/octet-stream")
    att.save(force_insert=True)

    url = Attachment._get_service("s3").service_url(att, as_attachment=True)
    with urlopen(url, timeout=5) as resp:
        disposition = resp.headers["Content-Disposition"]

    assert disposition == 'attachment; filename="data.bin"'


def test_service_url_uses_configured_expiration(app, minio, Attachment, db):
    """`url_expires_in` config flows through to the presigned URL."""
    from urllib.parse import parse_qs, urlparse

    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)

    service = S3(
        app,
        bucket=MINIO_BUCKET,
        endpoint=minio,
        access_key_id=MINIO_ROOT_USER,
        secret_access_key=MINIO_ROOT_PASSWORD,
        url_expires_in=60,
    )
    url = service.service_url(att)
    expires = parse_qs(urlparse(url).query)["X-Amz-Expires"][0]
    assert expires == "60"
