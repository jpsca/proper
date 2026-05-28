"""Integration tests for proper.storage.services.S3 against a MinIO container."""

from io import BytesIO
from unittest.mock import patch

import pytest

from proper import App, current
from proper.models import ProperModel
from proper.storage.services import S3


@pytest.fixture()
def app(tmp_path, minio, MINIO_BUCKET, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD):
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
            "s3_public": {
                "type": "S3",
                "bucket": MINIO_BUCKET,
                "endpoint": minio,
                "access_key_id": MINIO_ROOT_USER,
                "secret_access_key": MINIO_ROOT_PASSWORD,
                "public": True,
            },
        },
        "STORAGE_ALLOWED_INLINE": ["image/*", "application/pdf"],
        "STORAGE_ALLOWED_VARIANTS": ["image/png", "image/jpeg", "image/gif"],
        "STORAGE_FALLBACK_FORMAT": "png",
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


def _make_file(content=b"hello", filename="test.txt", content_type=""):
    buf = BytesIO(content)
    buf.filename = filename  # type: ignore
    buf.content_type = content_type  # type: ignore
    return buf


# --- S3 service - basic operations ---


def test_service_is_s3(Attachment):
    service = Attachment._get_service("s3")
    assert isinstance(service, S3)


def test_upload_and_download(Attachment):
    att = Attachment(_make_file(b"hello s3", "s3test.txt"))
    att.save(force_insert=True)
    assert att.download() == b"hello s3"


def test_upload_sets_byte_size(Attachment):
    att = Attachment(_make_file(b"12345", "f.txt"))
    att.save(force_insert=True)
    assert att.byte_size == 5


def test_upload_content_type(MINIO_BUCKET, Attachment):
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


def test_upload_handles_closed_file(Attachment):
    f = _make_file(b"some data", "f.txt")
    att = Attachment(f)
    att.save(force_insert=True)  # should not raise even if boto3 closes the stream


def test_download_different_files(Attachment):
    att1 = Attachment(_make_file(b"aaa", "a.txt"))
    att1.save(force_insert=True)
    att2 = Attachment(_make_file(b"bbb", "b.txt"))
    att2.save(force_insert=True)
    assert att1.download() == b"aaa"
    assert att2.download() == b"bbb"


# --- S3 service - key sharding ---


def test_key_uses_id_sharding(Attachment):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    service = Attachment._get_service("s3")
    key = service._get_key(att)
    att_id = str(att.id)
    assert key.startswith(f"{att_id[:2]}/")


# --- S3 service - purge ---


def test_purge_deletes_object(MINIO_BUCKET, Attachment):
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


def test_purge_deletes_record(Attachment):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    assert Attachment.select().count() == 1
    att.purge()
    assert Attachment.select().count() == 0


# --- S3 service - send_file ---


def test_send_file_inline(Attachment):
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


def test_send_file_as_attachment(Attachment):
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


# --- S3 service - round-trip through Attachment model ---


def test_fields_survive_round_trip(Attachment):
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


def test_download_after_reload(Attachment):
    att = Attachment(_make_file(b"round trip", "f.txt"))
    att.save(force_insert=True)
    loaded = Attachment.get_or_none(Attachment.id == att.id)
    assert loaded.download() == b"round trip"


# --- S3.service_url - presigned URLs ---


def test_service_url_returns_signed_url(Attachment):
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


def test_service_url_inline_by_default(Attachment):
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


def test_service_url_as_attachment_sets_download_disposition(Attachment):
    from urllib.request import urlopen

    att = Attachment(_make_file(b"x", "data.bin"), content_type="application/octet-stream")
    att.save(force_insert=True)

    url = Attachment._get_service("s3").service_url(att, as_attachment=True)
    with urlopen(url, timeout=5) as resp:
        disposition = resp.headers["Content-Disposition"]

    assert disposition == 'attachment; filename="data.bin"'


def test_service_url_uses_configured_expiration(app, minio, Attachment):
    """`url_expires_in` config flows through to the presigned URL."""
    from urllib.parse import parse_qs, urlparse

    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)

    service = S3(
        app,
        bucket="test-bucket",
        endpoint=minio,
        access_key_id="minioadmin",
        secret_access_key="minioadmin",
        url_expires_in=60,
    )
    url = service.service_url(att)
    expires = parse_qs(urlparse(url).query)["X-Amz-Expires"][0]
    assert expires == "60"


# --- S3.direct_upload_url - presigned PUT ---


def test_direct_upload_url_returns_signed_put(Attachment):
    att = Attachment.create_pending_blob(
        filename="x.png", content_type="image/png", byte_size=5,
    )
    upload = Attachment._get_service("s3").direct_upload_url(att)

    assert upload["url"].startswith("http")
    assert "X-Amz-Signature=" in upload["url"]
    assert upload["headers"]["Content-Type"] == "image/png"


def test_direct_upload_url_round_trip(Attachment):
    """A real PUT to the presigned URL stores the bytes; we can then GET
    them back via the same key. End-to-end smoke test."""
    from urllib.request import Request as URLRequest
    from urllib.request import urlopen

    att = Attachment.create_pending_blob(
        filename="rt.txt", content_type="text/plain", byte_size=5,
    )
    service = Attachment._get_service("s3")
    upload = service.direct_upload_url(att)

    req = URLRequest(
        upload["url"], data=b"hello", method="PUT",
        headers=upload["headers"],
    )
    with urlopen(req, timeout=5) as resp:
        assert resp.status in (200, 204)

    assert service.download(att) == b"hello"


def test_direct_upload_url_propagates_checksum(Attachment):
    att = Attachment.create_pending_blob(
        filename="x.txt", content_type="text/plain", byte_size=1,
    )
    upload = Attachment._get_service("s3").direct_upload_url(
        att, checksum="deadbeef==",
    )
    # The header is what the browser will send back on the PUT.
    assert upload["headers"]["Content-MD5"] == "deadbeef=="
    # SigV4 covers Content-MD5 via the signature, not as a query value -
    # the signed-headers list announces it. If S3 receives a PUT without
    # the matching header, the signature won't validate.
    assert "X-Amz-SignedHeaders=content-md5" in upload["url"]


# --- S3 public services ---


def test_public_service_url_is_unsigned(MINIO_BUCKET, Attachment):
    """`service_url()` on a public service returns the bucket's native
    URL with no presigning - the URL is stable and bears no expiry."""
    att = Attachment(
        _make_file(b"hi", "shot.png"),
        content_type="image/png",
        service_name="s3_public",
    )
    att.save(force_insert=True)

    url = Attachment._get_service("s3_public").service_url(att)

    assert url.startswith("http")
    assert "X-Amz-Signature=" not in url
    assert "X-Amz-Expires=" not in url
    # Path-style: <endpoint>/<bucket>/<key>
    assert f"/{MINIO_BUCKET}/" in url
    assert url.endswith(f"/{att.filename}")


def test_public_service_url_ignores_as_attachment(Attachment):
    """`as_attachment` is informational on public services - the URL is
    the same regardless. Disposition is decided by what was baked into
    Content-Type at upload time, not per-request."""
    att = Attachment(
        _make_file(b"x", "data.bin"),
        content_type="application/octet-stream",
        service_name="s3_public",
    )
    att.save(force_insert=True)

    service = Attachment._get_service("s3_public")
    assert service.service_url(att) == service.service_url(att, as_attachment=True)


def test_public_upload_passes_public_read_acl_to_boto(Attachment):
    """Objects uploaded to a public service pass `ACL=public-read` to boto3.

    Verified by intercepting the boto3 call rather than by reading the ACL
    back: MinIO accepts the parameter without surfacing it via `get_object_acl`
    (it uses bucket policies for public access instead of object-level ACLs).
    """
    service = Attachment._get_service("s3_public")
    captured = {}
    original_upload_fileobj = service.client.upload_fileobj

    def spy(file, bucket, key, ExtraArgs=None, **kw):
        captured["ExtraArgs"] = ExtraArgs or {}
        return original_upload_fileobj(file, bucket, key, ExtraArgs=ExtraArgs, **kw)

    with patch.object(service.client, "upload_fileobj", side_effect=spy):
        att = Attachment(
            _make_file(b"data", "f.txt"),
            content_type="text/plain",
            service_name="s3_public",
        )
        att.save(force_insert=True)

    assert captured["ExtraArgs"].get("ACL") == "public-read"
    assert captured["ExtraArgs"].get("ContentType") == "text/plain"


def test_private_upload_does_not_pass_acl(Attachment):
    """Sanity check: the default (non-public) service uploads without ACL."""
    service = Attachment._get_service("s3")
    captured = {}
    original_upload_fileobj = service.client.upload_fileobj

    def spy(file, bucket, key, ExtraArgs=None, **kw):
        captured["ExtraArgs"] = ExtraArgs or {}
        return original_upload_fileobj(file, bucket, key, ExtraArgs=ExtraArgs, **kw)

    with patch.object(service.client, "upload_fileobj", side_effect=spy):
        att = Attachment(_make_file(b"data", "f.txt"), content_type="text/plain")
        att.save(force_insert=True)

    assert "ACL" not in captured["ExtraArgs"]


def test_public_direct_upload_url_signs_acl_header(Attachment):
    """The presigned PUT for a public service includes `x-amz-acl` in the
    signed-headers list and returns the matching `x-amz-acl: public-read`
    header for the browser to send back on the PUT.

    With SigV4, `ACL` is signed as a request header (not as a query value),
    so the assertion looks at `X-Amz-SignedHeaders` rather than a literal
    `?ACL=...` in the URL.
    """
    att = Attachment.create_pending_blob(
        filename="x.png", content_type="image/png", byte_size=5,
        service_name="s3_public",
    )
    upload = Attachment._get_service("s3_public").direct_upload_url(att)

    assert "x-amz-acl" in upload["url"].lower().split("x-amz-signedheaders=")[1]
    assert upload["headers"]["x-amz-acl"] == "public-read"


def test_public_direct_upload_round_trip(Attachment):
    """End-to-end PUT to the presigned public URL with the returned headers
    succeeds. Validates that the signed `ACL` param and the `x-amz-acl`
    header agree (S3 rejects the PUT otherwise — signature mismatch)."""
    from urllib.request import Request as URLRequest
    from urllib.request import urlopen

    att = Attachment.create_pending_blob(
        filename="rt.txt", content_type="text/plain", byte_size=5,
        service_name="s3_public",
    )
    service = Attachment._get_service("s3_public")
    upload = service.direct_upload_url(att)

    req = URLRequest(
        upload["url"], data=b"hello", method="PUT",
        headers=upload["headers"],
    )
    with urlopen(req, timeout=5) as resp:
        assert resp.status in (200, 204)

    assert service.download(att) == b"hello"
