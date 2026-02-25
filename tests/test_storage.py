"""Tests for proper.storage — Attachment model, Storage class, Disk service, and variants."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import peewee as pw
import pytest

from proper import App
from proper.errors import StorageConfigError
from proper.storage import Storage
from proper.storage.attachment import DEFAULT_CONTENT_TYPE, get_attachment_mixin
from proper.storage.imageops import blur, grayscale, sepia
from proper.storage.services import Disk


# ── helpers ─────────────────────────────────────────────────────────


STORAGE_SERVICES = {
    "local": {"type": "Disk", "root": "temp/storage"},
    "other": {"type": "Disk", "root": "temp/other"},
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
        "STORAGE_ALLOWED_INLINE_CONTENT_TYPES": ["image/", "application/pdf"],
        "QUEUE": {
            "type": "huey.MemoryHuey",
            "immediate": True,
            "immediate_use_memory": True,
        },
    }
    app = App("tests", config)
    app.root_path = tmp_path / "app"
    app.root_path.mkdir(parents=True, exist_ok=True)
    app.storage = Storage(app)
    return app


@pytest.fixture()
def Attachment(app):
    return app.storage.Attachment


@pytest.fixture()
def db(Attachment):
    database = pw.SqliteDatabase(":memory:")
    Attachment.bind(database)
    database.create_tables([Attachment])
    yield database
    database.close()


# ═══════════════════════════════════════════════════════════════════
# Attachment.__init__
# ═══════════════════════════════════════════════════════════════════


def test_default_service_name_from_config(Attachment, db):
    att = Attachment(_make_file())
    assert att.service_name == "local"


def test_explicit_service_name(Attachment, db):
    att = Attachment(_make_file(), service_name="other")
    assert att.service_name == "other"


def test_missing_service_name_raises():
    storage = MagicMock()
    Att = get_attachment_mixin(storage, default_service_name="")
    database = pw.SqliteDatabase(":memory:")
    Att.bind(database)
    with pytest.raises(StorageConfigError, match="Missing"):
        Att(_make_file())
    database.close()


def test_filename_parameterized(Attachment, db):
    att = Attachment(_make_file(filename="My Photo (1).JPG"))
    assert att.filename == "my-photo-1.jpg"


def test_filename_from_filesto_attribute(Attachment, db):
    att = Attachment(_make_file(filename="report.pdf"))
    assert att.filename == "report.pdf"


def test_filename_without_extension(Attachment, db):
    att = Attachment(_make_file(filename="README"))
    assert att.filename == "readme"


def test_content_type_detected_from_filename(Attachment, db):
    att = Attachment(_make_file(filename="photo.jpg"))
    assert att.content_type == "image/jpeg"


def test_content_type_explicit(Attachment, db):
    att = Attachment(_make_file(), content_type="application/json")
    assert att.content_type == "application/json"


def test_content_type_from_filesto_attribute(Attachment, db):
    f = _make_file(filename="data")
    f.content_type = "text/csv"
    att = Attachment(f)
    assert att.content_type == "text/csv"


def test_content_type_default_fallback(Attachment, db):
    att = Attachment(_make_file(filename=""))
    assert att.content_type == DEFAULT_CONTENT_TYPE


def test_public_defaults_to_false(Attachment, db):
    att = Attachment(_make_file())
    assert att.public is False


def test_public_explicit(Attachment, db):
    att = Attachment(_make_file(), public=True)
    assert att.public is True


def test_byte_size_default(Attachment, db):
    att = Attachment(_make_file())
    assert att.byte_size == 0


# ═══════════════════════════════════════════════════════════════════
# Attachment.save — upload on first save
# ═══════════════════════════════════════════════════════════════════


def test_save_uploads_and_persists(Attachment, db):
    att = Attachment(_make_file(b"some data", "doc.txt"))
    att.save(force_insert=True)
    assert att.byte_size == 9
    assert Attachment.select().count() == 1


def test_second_save_does_not_reupload(Attachment, db):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    original_size = att.byte_size
    assert original_size == 4
    # Mutate byte_size and save again — file should not be re-uploaded
    att.byte_size = 999
    att.save()
    reloaded = Attachment.get_or_none(Attachment.id == att.id)
    assert reloaded.byte_size == 999


# ═══════════════════════════════════════════════════════════════════
# Attachment.download
# ═══════════════════════════════════════════════════════════════════


def test_download_returns_bytes(Attachment, db):
    content = b"file contents here"
    att = Attachment(_make_file(content, "readme.txt"))
    att.save(force_insert=True)
    assert att.download() == content


def test_download_different_files(Attachment, db):
    att1 = Attachment(_make_file(b"aaa", "a.txt"))
    att1.save(force_insert=True)
    att2 = Attachment(_make_file(b"bbb", "b.txt"))
    att2.save(force_insert=True)
    assert att1.download() == b"aaa"
    assert att2.download() == b"bbb"


# ═══════════════════════════════════════════════════════════════════
# Attachment round-trip (save → load from DB)
# ═══════════════════════════════════════════════════════════════════


def test_fields_survive_round_trip(Attachment, db):
    att = Attachment(
        _make_file(b"data", "photo.jpg"),
        content_type="image/jpeg",
        public=True,
    )
    att.save(force_insert=True)
    loaded = Attachment.get_or_none(Attachment.id == att.id)
    assert loaded.service_name == "local"
    assert loaded.filename == "photo.jpg"
    assert loaded.content_type == "image/jpeg"
    assert loaded.public is True
    assert loaded.byte_size == 4


def test_download_after_reload(Attachment, db):
    att = Attachment(_make_file(b"round trip", "f.txt"))
    att.save(force_insert=True)
    loaded = Attachment.get_or_none(Attachment.id == att.id)
    assert loaded.download() == b"round trip"


# ═══════════════════════════════════════════════════════════════════
# Attachment.purge
# ═══════════════════════════════════════════════════════════════════


def test_purge_deletes_file_and_record(Attachment, db):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    assert Attachment.select().count() == 1
    att.purge()
    assert Attachment.select().count() == 0


def test_purge_file_no_longer_downloadable(Attachment, db):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    att.purge()
    assert Attachment.get_or_none(Attachment.id == att.id) is None


# ═══════════════════════════════════════════════════════════════════
# Disk service
# ═══════════════════════════════════════════════════════════════════


def test_upload_creates_file(app, Attachment, db):
    att = Attachment(_make_file(b"hello", "test.txt"))
    att.save(force_insert=True)
    service = app.storage.get_service("local")
    path = service._get_path(att)
    assert path.exists()
    assert path.read_bytes() == b"hello"


def test_upload_sets_byte_size(Attachment, db):
    att = Attachment(_make_file(b"12345", "f.txt"))
    att.save(force_insert=True)
    assert att.byte_size == 5


def test_purge_removes_file(app, Attachment, db):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    service = app.storage.get_service("local")
    path = service._get_path(att)
    assert path.exists()
    att.purge()
    assert not path.exists()


def test_path_uses_id_sharding(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    service = app.storage.get_service("local")
    path = service._get_path(att)
    key = str(att.id)
    assert path.parent.parent.name == key[:2]
    assert path.parent.name == key[2:4]


# ═══════════════════════════════════════════════════════════════════
# Storage.get_service
# ═══════════════════════════════════════════════════════════════════


def test_returns_disk_service(app):
    service = app.storage.get_service("local")
    assert isinstance(service, Disk)


def test_caches_service_instance(app):
    s1 = app.storage.get_service("local")
    s2 = app.storage.get_service("local")
    assert s1 is s2


def test_unknown_service_raises(app):
    with pytest.raises(ValueError, match="Unknown service type"):
        app.storage.get_service("nonexistent")


def test_different_services_are_independent(app):
    s1 = app.storage.get_service("local")
    s2 = app.storage.get_service("other")
    assert s1 is not s2


# ═══════════════════════════════════════════════════════════════════
# Storage.url_for
# ═══════════════════════════════════════════════════════════════════


def test_url_for_private(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"), public=False)
    att.save(force_insert=True)
    with patch.object(app, "url_for", return_value="/att/signed") as mock:
        url = app.storage.url_for(att)
    assert url == "/att/signed"
    assert mock.call_args[0][0] == "Attachment.show"
    assert "signed_pk" in mock.call_args[1]


def test_url_for_public(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"), public=True)
    att.save(force_insert=True)
    with patch.object(app, "url_for", return_value="/pub/123") as mock:
        url = app.storage.url_for(att)
    assert url == "/pub/123"
    mock.assert_called_once_with("PublicAttachment.show", pk=att.id)


# ═══════════════════════════════════════════════════════════════════
# Storage.get_public_attachment / get_attachment
# ═══════════════════════════════════════════════════════════════════


def test_get_public_attachment(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"), public=True)
    att.save(force_insert=True)
    found = app.storage.get_public_attachment(att.id)
    assert found.id == att.id


def test_get_attachment_valid_signature(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    signed_pk = app.storage.signer.sign(str(att.id))
    found = app.storage.get_attachment(signed_pk)
    assert found.id == att.id


def test_get_attachment_invalid_signature(app, Attachment, db):
    result = app.storage.get_attachment("bad.signature.value")
    assert result is None


def test_get_attachment_invalid_signature_debug_raises(tmp_path, Attachment, db):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": True,
        "STORAGE": "local",
        "STORAGE_SERVICES": STORAGE_SERVICES,
    }
    from proper.errors import BadSignature
    debug_app = App("tests", config)
    debug_app.root_path = tmp_path / "debug_app"
    debug_app.root_path.mkdir(parents=True, exist_ok=True)
    debug_app.storage = Storage(debug_app)
    with pytest.raises(BadSignature):
        debug_app.storage.get_attachment("bad.signature.value")


def test_get_attachment_zero_max_age_uses_default(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    signed_pk = app.storage.signer.sign(str(att.id))
    found = app.storage.get_attachment(signed_pk, max_age=0)
    assert found.id == att.id


# ═══════════════════════════════════════════════════════════════════
# Storage.send_file
# ═══════════════════════════════════════════════════════════════════


def test_send_file_delegates_to_service(app, Attachment, db):
    att = Attachment(
        _make_file(b"data", "photo.png"),
        content_type="image/png",
    )
    att.save(force_insert=True)
    mock_response = MagicMock()
    with patch("proper.storage.storage.current") as mock_current:
        mock_current.response = mock_response
        app.storage.send_file(att)
    _service = app.storage.get_service("local")
    # Verify send_file was invoked on the response (Disk.send_file calls response.send_file)
    mock_response.send_file.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# Storage._is_inline_content_type
# ═══════════════════════════════════════════════════════════════════


def test_image_is_inline(app):
    assert app.storage._is_inline_content_type("image/png") is True
    assert app.storage._is_inline_content_type("application/pdf") is True
    assert app.storage._is_inline_content_type("application/octet-stream") is False
    assert app.storage._is_inline_content_type("text/plain") is False


# ═══════════════════════════════════════════════════════════════════
# Variant fields on Attachment
# ═══════════════════════════════════════════════════════════════════


def test_parent_defaults_to_none(Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    reloaded = Attachment.get_or_none(Attachment.id == att.id)
    assert reloaded.parent_id is None


def test_variant_key_defaults_to_empty(Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"))
    assert att.variant_key == ""


def test_public_inherited_from_parent(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"), public=True)
    parent.save(force_insert=True)
    child = Attachment(_make_file(b"y", "v.txt"), parent=parent)
    assert child.public is True


def test_public_inherited_false_from_parent(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"), public=False)
    parent.save(force_insert=True)
    child = Attachment(_make_file(b"y", "v.txt"), parent=parent)
    assert child.public is False


def test_public_explicit_overrides_parent(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"), public=True)
    parent.save(force_insert=True)
    child = Attachment(_make_file(b"y", "v.txt"), parent=parent, public=False)
    assert child.public is False


def test_public_defaults_false_without_parent(Attachment, db):
    att = Attachment(_make_file())
    assert att.public is False


# ═══════════════════════════════════════════════════════════════════
# Attachment._variant_key
# ═══════════════════════════════════════════════════════════════════


def test_deterministic(Attachment):
    k1 = Attachment._variant_key(resize=(100, 100))
    k2 = Attachment._variant_key(resize=(100, 100))
    assert k1 == k2


def test_different_values_produce_different_keys(Attachment):
    k1 = Attachment._variant_key(resize=(100, 100))
    k2 = Attachment._variant_key(resize=(200, 200))
    assert k1 != k2


def test_different_keys_produce_different_hashes(Attachment):
    k1 = Attachment._variant_key(resize=(100, 100))
    k2 = Attachment._variant_key(crop=(100, 100))
    assert k1 != k2


def test_different_order_produce_different_keys(Attachment):
    k1 = Attachment._variant_key(rotate=90, resize=(200, 200))
    k2 = Attachment._variant_key(resize=(200, 200), rotate=90)
    assert k1 != k2


# ═══════════════════════════════════════════════════════════════════
# Attachment.create_variant
# ═══════════════════════════════════════════════════════════════════


def test_creates_variant_record(Attachment, db):
    parent = Attachment(_make_file(b"original", "photo.jpg"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"thumb", "thumb.jpg"))
    assert Attachment.select().count() == 2
    reloaded = Attachment.get_or_none(Attachment.id == v.id)
    assert reloaded is not None


def test_inherits_service_name(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"))
    assert v.service_name == parent.service_name


def test_inherits_public(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"), public=True)
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"))
    assert v.public is True


def test_override_service_name(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"), service_name="other")
    assert v.service_name == "other"


def test_variant_is_saved(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"))
    reloaded = Attachment.get_or_none(Attachment.id == v.id)
    assert reloaded is not None
    assert reloaded.service_name == parent.service_name


def test_variant_file_is_downloadable(Attachment, db):
    parent = Attachment(_make_file(b"original", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"transformed", "v.txt"))
    assert v.download() == b"transformed"


def test_variant_key_stored(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"), variant_key="abc123")
    assert v.variant_key == "abc123"


def test_metadata_stored(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(
        _make_file(b"y", "v.txt"),
        metadata={"transformations": {"resize": [100, 100]}},
    )
    assert v.metadata["transformations"] == {"resize": [100, 100]}


# ═══════════════════════════════════════════════════════════════════
# Attachment.variant
# ═══════════════════════════════════════════════════════════════════


def test_no_transformations_raises_for_unsupported(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.zip"), content_type="application/zip")
    parent.save(force_insert=True)
    with pytest.raises(ValueError, match="not supported"):
        parent.variant()


def test_raises_for_unsupported_content_type(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.zip"), content_type="application/zip")
    parent.save(force_insert=True)
    with pytest.raises(ValueError, match="not supported"):
        parent.variant(resize=(100, 100))


def test_dispatches_to_transform_image(Attachment, db):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    transformed = _make_file(b"thumb", "thumb.jpg")
    with patch.object(parent, "transform_image", return_value=transformed):
        v = parent.variant(resize=(100, 100))
    assert v.download() == b"thumb"


def test_returns_existing_variant(Attachment, db):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    transformed = _make_file(b"thumb", "thumb.jpg")
    with patch.object(parent, "transform_image", return_value=transformed) as mock:
        v1 = parent.variant(resize=(100, 100))
        v2 = parent.variant(resize=(100, 100))
    assert v1.id == v2.id
    # transform_image called only once
    mock.assert_called_once()


def test_different_transformations_create_different_variants(Attachment, db):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)

    with patch.object(
        parent,
        "transform_image",
        side_effect=[
            _make_file(b"small", "s.jpg"),
            _make_file(b"large", "l.jpg"),
        ],
    ):
        v1 = parent.variant(resize=(100, 100))
        v2 = parent.variant(resize=(200, 200))

    assert v1.id != v2.id


def test_stores_ops_in_metadata(Attachment, db):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    transformed = _make_file(b"thumb", "thumb.jpg")
    with patch.object(parent, "transform_image", return_value=transformed):
        v = parent.variant(resize=(100, 100), quality=80)
    assert v.metadata["ops"]["resize"] == (100, 100)
    assert v.metadata["ops"]["quality"] == 80


def test_stores_variant_key(Attachment, db):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    expected_key = Attachment._variant_key(resize=(100, 100))
    transformed = _make_file(b"thumb", "thumb.jpg")
    with patch.object(parent, "transform_image", return_value=transformed):
        v = parent.variant(resize=(100, 100))
    assert v.variant_key == expected_key


# ═══════════════════════════════════════════════════════════════════
# Attachment.variants backref
# ═══════════════════════════════════════════════════════════════════


def test_variants_empty_by_default(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    assert list(parent.variants) == []


def test_variants_lists_children(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v1 = parent.create_variant(_make_file(b"a", "a.txt"))
    v2 = parent.create_variant(_make_file(b"b", "b.txt"))
    variant_ids = {v.id for v in parent.variants}
    assert variant_ids == {v1.id, v2.id}


# ═══════════════════════════════════════════════════════════════════
# Attachment.transform_image / video / pdf — delegate to functions
# ═══════════════════════════════════════════════════════════════════


def test_transform_image_calls_function(Attachment, db):
    att = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    att.save(force_insert=True)
    with patch("proper.storage.attachment.transform_image") as mock:
        mock.return_value = b"result"
        result = att.transform_image(b"img", resize=(100, 100))
    mock.assert_called_once_with(b"img", resize=(100, 100))
    assert result == b"result"


def test_transform_image_delegates_to_imageops(Attachment, db):
    att = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    att.save(force_insert=True)
    with patch("proper.storage.attachment.transform_image") as mock:
        mock.return_value = b"transformed"
        att.transform_image("/path/to/image.jpg", resize_to_limit=(400, 400))
    mock.assert_called_once_with("/path/to/image.jpg", resize_to_limit=(400, 400))


# ═══════════════════════════════════════════════════════════════════
# Custom SUPPORTED_VARIANT_TYPES via subclass
# ═══════════════════════════════════════════════════════════════════


def test_subclass_can_add_content_types(Attachment, db):
    class MyAttachment(Attachment):
        SUPPORTED_VARIANT_TYPES = {
            **Attachment.SUPPORTED_VARIANT_TYPES,
            "application/epub": "transform_epub",
        }

        def transform_epub(self, source, **transformations):
            return _make_file(b"epub-thumb", "cover.png")

        class Meta:
            table_name = Attachment._meta.table_name

    parent = MyAttachment(
        _make_file(b"book", "book.epub"), content_type="application/epub"
    )
    parent.save(force_insert=True)
    v = parent.variant(thumbnail=True)
    assert v.download() == b"epub-thumb"


def test_custom_transform_can_delegate_to_transform_image(Attachment, db):
    class MyAttachment(Attachment):
        SUPPORTED_VARIANT_TYPES = {
            **Attachment.SUPPORTED_VARIANT_TYPES,
            "application/pdf": "transform_pdf",
        }

        def transform_pdf(self, source, **transformations):
            # Simulate extracting a page as an image
            extracted = b"extracted-image"
            return self.transform_image(extracted, **transformations)

        class Meta:
            table_name = Attachment._meta.table_name

    parent = MyAttachment(
        _make_file(b"pdf-data", "doc.pdf"), content_type="application/pdf"
    )
    parent.save(force_insert=True)
    result = _make_file(b"processed", "page.png")
    with patch.object(parent, "transform_image", return_value=result) as mock:
        v = parent.variant(resize=(100, 100))
    mock.assert_called_once_with(b"extracted-image", resize=(100, 100))
    assert v.download() == b"processed"


# ═══════════════════════════════════════════════════════════════════
# imageops — sepia and grayscale filters
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture()
def rgb_image():
    """Create a simple 2x2 RGB pyvips image."""
    pyvips = pytest.importorskip("pyvips")
    # 2x2 red image (255, 0, 0) in sRGB
    image = pyvips.Image.black(2, 2, bands=3).add([255, 0, 0]).cast("uchar")
    return image.copy(interpretation=pyvips.Interpretation.SRGB)


@pytest.fixture()
def rgba_image(rgb_image):
    """Create a 2x2 RGBA image with full opacity."""
    return rgb_image.addalpha()


def test_sepia_returns_3_band_image(rgb_image):
    result = sepia(rgb_image)
    assert result.bands == 3


def test_sepia_preserves_alpha(rgba_image):
    result = sepia(rgba_image)
    assert result.bands == 4
    assert result.hasalpha()


def test_default_produces_warm_tones(rgb_image):
    result = sepia(rgb_image)
    # For a pure red input, R channel should be brightest
    pixel = result(0, 0)
    assert pixel[0] > pixel[1] > pixel[2]


def test_custom_tone(rgb_image):
    # Equal multipliers should produce identical channels (grayscale)
    result = sepia(rgb_image, 1.0, 1.0, 1.0)
    pixel = result(0, 0)
    assert pixel[0] == pixel[1] == pixel[2]


def test_grayscale_returns_3_band_image(rgb_image):
    result = grayscale(rgb_image)
    assert result.bands == 3


def test_grayscale_all_channels_equal(rgb_image):
    result = grayscale(rgb_image)
    pixel = result(0, 0)
    assert pixel[0] == pixel[1] == pixel[2]


def test_grayscale_preserves_alpha(rgba_image):
    result = grayscale(rgba_image)
    assert result.bands == 4
    assert result.hasalpha()


def test_custom_weights(rgb_image):
    # Only red channel contributes → pure red input → bright gray
    bright = grayscale(rgb_image, 1.0, 0.0, 0.0)
    # Only green channel contributes → pure red input → black
    dark = grayscale(rgb_image, 0.0, 1.0, 0.0)
    assert bright(0, 0)[0] > dark(0, 0)[0]


def test_returns_image(rgb_image):
    result = blur(rgb_image, 1.5)
    assert result.width == rgb_image.width
    assert result.height == rgb_image.height
    assert result.bands == rgb_image.bands


def test_preserves_alpha(rgba_image):
    result = blur(rgba_image, 1.5)
    assert result.bands == 4
    assert result.hasalpha()


# ═══════════════════════════════════════════════════════════════════
# Storage.purge_variants
# ═══════════════════════════════════════════════════════════════════


def test_purge_variants_deletes_variant_records(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    parent.create_variant(_make_file(b"a", "a.txt"))
    parent.create_variant(_make_file(b"b", "b.txt"))
    assert Attachment.select().count() == 3
    parent.purge_variants()
    assert Attachment.select().count() == 1
    assert Attachment.get_or_none(Attachment.id == parent.id)


def test_purge_variants_removes_files(app, Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"a", "a.txt"))
    service = app.storage.get_service(v.service_name)
    path = service._get_path(v)
    assert path.exists()
    parent.purge_variants()
    assert not path.exists()


def test_purge_parent_cascades_to_variants(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    parent.create_variant(_make_file(b"a", "a.txt"))
    parent.create_variant(_make_file(b"b", "b.txt"))
    parent.purge()
    assert Attachment.select().count() == 0


def test_purge_variants_on_attachment_with_no_variants(Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    parent.purge_variants()  # should not raise
    assert Attachment.select().count() == 1


# ═══════════════════════════════════════════════════════════════════
# Storage.purge — later
# ═══════════════════════════════════════════════════════════════════


def test_purge_later_enqueues(app, Attachment, db):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    service = app.storage.get_service("local")
    path = service._get_path(att)
    assert path.exists()
    assert Attachment.select().count() == 1
    att.purge_later()
    assert not path.exists()
    assert Attachment.select().count() == 0


def test_purge_variants_later_enqueues(app, Attachment, db):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"a", "a.txt"))
    service = app.storage.get_service(v.service_name)
    path = service._get_path(v)
    assert path.exists()
    assert Attachment.select().count() == 2
    parent.purge_variants_later()
    assert not path.exists()
    assert Attachment.select().count() == 1
    assert Attachment.get_or_none(Attachment.id == parent.id) is not None
