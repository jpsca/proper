from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from proper import App, current
from proper.models import ProperModel
from proper.storage.attachment import DEFAULT_CONTENT_TYPE
from proper.storage.services import Disk


@pytest.fixture()
def app(tmp_path):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        "STORAGE": "local",
        "STORAGE_SERVICES": {
            "local": {"type": "Disk", "root": "temp/storage"},
            "other": {"type": "Disk", "root": "temp/other"},
            "public": {"type": "Disk", "root": "temp/public", "public": True},
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


def test_attachment_for_is_memoized(app, BaseModel):
    """Repeated calls with the same base must return the *same* class -
    otherwise VARIANTS_ENABLED_FOR extension and the per-class service
    cache split across instances.
    """
    a = app.attachment_for(BaseModel)
    b = app.attachment_for(BaseModel)
    assert a is b


def test_attachment_for_different_bases_are_distinct(app, BaseModel):
    """Different bases must produce different classes."""

    class OtherBase(ProperModel):
        pass

    a = app.attachment_for(BaseModel)
    b = app.attachment_for(OtherBase)
    assert a is not b


# --- Attachment.__init__ ---


def test_default_service_name_from_config(app, Attachment):
    att = Attachment(_make_file())
    assert att.service_name == app.config["STORAGE"]


def test_explicit_service_name(Attachment):
    att = Attachment(_make_file(), service_name="other")
    assert att.service_name == "other"


def test_filename_parameterized(Attachment):
    att = Attachment(_make_file(filename="My Photo (1).JPG"))
    assert att.filename == "my-photo-1.jpg"


def test_filename_from_upload_attribute(Attachment):
    att = Attachment(_make_file(filename="report.pdf"))
    assert att.filename == "report.pdf"


def test_filename_without_extension(Attachment):
    att = Attachment(_make_file(filename="README"))
    assert att.filename == "readme"


def test_content_type_detected_from_filename(Attachment):
    att = Attachment(_make_file(filename="photo.jpg"))
    assert att.content_type == "image/jpeg"


def test_content_type_explicit(Attachment):
    att = Attachment(_make_file(), content_type="application/json")
    assert att.content_type == "application/json"


def test_content_type_from_upload_attribute(Attachment):
    f = _make_file(filename="data", content_type="text/csv")
    att = Attachment(f)
    assert att.content_type == "text/csv"


def test_content_type_default_fallback(Attachment):
    att = Attachment(_make_file(filename=""))
    assert att.content_type == DEFAULT_CONTENT_TYPE


def test_byte_size_default(Attachment):
    att = Attachment(_make_file())
    assert att.byte_size == 0


# --- Attachment.save - upload on first save ---


def test_save_uploads_and_persists(Attachment):
    att = Attachment(_make_file(b"some data", "doc.txt"))
    att.save(force_insert=True)
    assert att.byte_size == 9
    assert Attachment.select().count() == 1


def test_second_save_does_not_reupload(Attachment):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    original_size = att.byte_size
    assert original_size == 4
    # Mutate byte_size and save again - file should not be re-uploaded
    att.byte_size = 999
    att.save()
    reloaded = Attachment.get_or_none(Attachment.id == att.id)
    assert reloaded.byte_size == 999


def test_first_save_inserts_without_explicit_force_insert(Attachment):
    """Bare `Attachment(upload).save()` (no `force_insert=True`) must INSERT.

    `UUIDField(default=uuid4)` populates the PK at __init__, which would
    otherwise make peewee's default save() issue an UPDATE that matches
    zero rows and silently no-op. The presence of `_upload` is the
    "this is a fresh instance" signal we use to force INSERT.
    """
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save()  # ← no force_insert
    assert Attachment.select().count() == 1
    assert Attachment.get_or_none(Attachment.id == att.id) is not None


# --- Attachment.download ---


def test_download_returns_bytes(Attachment):
    content = b"file contents here"
    att = Attachment(_make_file(content, "readme.txt"))
    att.save(force_insert=True)
    assert att.download() == content


def test_download_different_files(Attachment):
    att1 = Attachment(_make_file(b"aaa", "a.txt"))
    att1.save(force_insert=True)
    att2 = Attachment(_make_file(b"bbb", "b.txt"))
    att2.save(force_insert=True)
    assert att1.download() == b"aaa"
    assert att2.download() == b"bbb"


# --- Attachment round-trip (save → load from DB) ---


def test_fields_survive_round_trip(Attachment):
    att = Attachment(
        _make_file(b"data", "photo.jpg"),
        content_type="image/jpeg",
    )
    att.save(force_insert=True)
    loaded = Attachment.get_or_none(Attachment.id == att.id)
    assert loaded.service_name == "local"
    assert loaded.filename == "photo.jpg"
    assert loaded.content_type == "image/jpeg"
    assert loaded.byte_size == 4


def test_download_after_reload(Attachment):
    att = Attachment(_make_file(b"round trip", "f.txt"))
    att.save(force_insert=True)
    loaded = Attachment.get_or_none(Attachment.id == att.id)
    assert loaded.download() == b"round trip"


# --- Attachment.purge ---


def test_purge_deletes_file_and_record(Attachment):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    assert Attachment.select().count() == 1
    att.purge()
    assert Attachment.select().count() == 0


def test_purge_file_no_longer_downloadable(Attachment):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    att.purge()
    assert Attachment.get_or_none(Attachment.id == att.id) is None


# --- Disk service ---


def test_upload_creates_file(Attachment):
    att = Attachment(_make_file(b"hello", "test.txt"))
    att.save(force_insert=True)
    service = Attachment._get_service("local")
    path = service._get_path(att)
    assert path.exists()
    assert path.read_bytes() == b"hello"


def test_upload_sets_byte_size(Attachment):
    att = Attachment(_make_file(b"12345", "f.txt"))
    att.save(force_insert=True)
    assert att.byte_size == 5


def test_purge_removes_file(Attachment):
    att = Attachment(_make_file(b"data", "f.txt"))
    att.save(force_insert=True)
    service = Attachment._get_service("local")
    path = service._get_path(att)
    assert path.exists()
    att.purge()
    assert not path.exists()


def test_path_uses_id_sharding(Attachment):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    service = Attachment._get_service("local")
    path = service._get_path(att)
    key = str(att.id)
    assert path.parent.parent.name == key[:2]
    assert path.parent.name == key[2:4]


# --- Storage.get_service ---


def test_returns_disk_service(Attachment):
    service = Attachment._get_service("local")
    assert isinstance(service, Disk)


def test_caches_service_instance(Attachment):
    s1 = Attachment._get_service("local")
    s2 = Attachment._get_service("local")
    assert s1 is s2


def test_unknown_service_raises(Attachment):
    with pytest.raises(ValueError, match="Unknown service type"):
        Attachment._get_service("nonexistent")


def test_different_services_are_independent(Attachment):
    s1 = Attachment._get_service("local")
    s2 = Attachment._get_service("other")
    assert s1 is not s2


# --- Storage.send_file ---


def test_send_file_delegates_to_service(Attachment):
    att = Attachment(
        _make_file(b"data", "photo.png"),
        content_type="image/png",
    )
    att.save(force_insert=True)
    mock_response = MagicMock()
    with patch("proper.storage.attachment.current") as mock_current:
        mock_current.response = mock_response
        att.send_file()
    # Verify send_file was invoked on the response (Disk.send_file calls response.send_file)
    mock_response.send_file.assert_called_once()


# --- Attachment.is_allowed_inline ---


def test_image_is_inline(Attachment):
    assert Attachment.is_allowed_inline("image/png") is True
    assert Attachment.is_allowed_inline("application/pdf") is True
    assert Attachment.is_allowed_inline("application/octet-stream") is False
    assert Attachment.is_allowed_inline("text/plain") is False


# --- Variant fields on Attachment ---


def test_parent_defaults_to_none(Attachment):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    reloaded = Attachment.get_or_none(Attachment.id == att.id)
    assert reloaded.parent_id is None


def test_variant_key_defaults_to_empty(Attachment):
    att = Attachment(_make_file(b"x", "f.txt"))
    assert att.variant_key == ""


# --- Attachment._variant_key ---


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


# --- Attachment.create_variant ---


def test_creates_variant_record(Attachment):
    parent = Attachment(_make_file(b"original", "photo.jpg"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"thumb", "thumb.jpg"))
    assert Attachment.select().count() == 2
    reloaded = Attachment.get_or_none(Attachment.id == v.id)
    assert reloaded is not None


def test_inherits_service_name(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"))
    assert v.service_name == parent.service_name


def test_variant_in_public_service_keeps_public_url(Attachment):
    # Variants inherit the parent's service_name, so a parent in a public
    # service produces a variant in the same public service.
    parent = Attachment(_make_file(b"x", "f.txt"), service_name="public")
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"))
    assert v.service_name == "public"
    assert v.service.public is True


def test_override_service_name(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"), service_name="other")
    assert v.service_name == "other"


def test_variant_is_saved(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"))
    reloaded = Attachment.get_or_none(Attachment.id == v.id)
    assert reloaded is not None
    assert reloaded.service_name == parent.service_name


def test_variant_file_is_downloadable(Attachment):
    parent = Attachment(_make_file(b"original", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"transformed", "v.txt"))
    assert v.download() == b"transformed"


def test_variant_key_stored(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"y", "v.txt"), variant_key="abc123")
    assert v.variant_key == "abc123"


def test_metadata_stored(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(
        _make_file(b"y", "v.txt"),
        metadata={"transformations": {"resize": [100, 100]}},
    )
    assert v.metadata["transformations"] == {"resize": [100, 100]}


# --- Attachment.variant ---


def test_no_transformations_raises_for_unsupported(Attachment):
    parent = Attachment(_make_file(b"x", "f.zip"), content_type="application/zip")
    parent.save(force_insert=True)
    with pytest.raises(ValueError, match="not supported"):
        parent.variant()


def test_raises_for_unsupported_content_type(Attachment):
    parent = Attachment(_make_file(b"x", "f.zip"), content_type="application/zip")
    parent.save(force_insert=True)
    with pytest.raises(ValueError, match="not supported"):
        parent.variant(resize=(100, 100))



def test_returns_existing_variant(Attachment):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    with (
        patch.object(parent, "preview_image", return_value=b"extracted") as preview_mock,
        patch("proper.storage.attachment.transform_image", return_value=b"thumb"),
    ):
        v1 = parent.variant(resize=(100, 100))
        v2 = parent.variant(resize=(100, 100))
    assert v1.id == v2.id
    # preview_image called only once (second variant() short-circuits on the cached row)
    preview_mock.assert_called_once()


def test_different_transformations_create_different_variants(Attachment):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)

    with (
        patch.object(parent, "preview_image", side_effect=[b"small", b"large"]),
        patch(
            "proper.storage.attachment.transform_image",
            side_effect=[b"small-thumb", b"large-thumb"],
        ),
    ):
        v1 = parent.variant(resize=(100, 100))
        v2 = parent.variant(resize=(200, 200))

    assert v1.id != v2.id


def test_stores_ops_in_metadata(Attachment):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    with (
        patch.object(parent, "preview_image", return_value=b"extracted"),
        patch("proper.storage.attachment.transform_image", return_value=b"thumb"),
    ):
        v = parent.variant(resize=(100, 100), quality=80)
    assert v.metadata["ops"]["resize"] == (100, 100)
    assert v.metadata["ops"]["quality"] == 80


def test_stores_variant_key(Attachment):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    # The key reflects the resolved save format, which `variant()` injects
    # into ops before hashing - so we replay the same resolution here.
    expected_key = Attachment._variant_key(resize=(100, 100), save={"format": "jpg"})
    with (
        patch.object(parent, "preview_image", return_value=b"extracted"),
        patch("proper.storage.attachment.transform_image", return_value=b"thumb"),
    ):
        v = parent.variant(resize=(100, 100))
    assert v.variant_key == expected_key


def test_variant_preserves_source_format_when_allowed(Attachment):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    with (
        patch.object(parent, "preview_image", return_value=b"extracted") as preview_mock,
        patch("proper.storage.attachment.transform_image", return_value=b"thumb") as transform_mock,
    ):
        v = parent.variant(resize=(100, 100))
    # The resolved save format is forwarded through to both the previewer
    # (in case it cares) and to transform_image (which actually encodes).
    assert preview_mock.call_args.kwargs["save"]["format"] == "jpg"
    assert transform_mock.call_args.kwargs["save"]["format"] == "jpg"
    assert v.filename.endswith(".jpg")
    assert v.content_type == "image/jpeg"


def test_variant_uses_fallback_format_when_source_not_allowed(Attachment):
    # image/bmp matches VARIANTS_ENABLED_FOR ("image/*") but is not in
    # STORAGE_ALLOWED_VARIANTS, so the variant should fall back to PNG.
    parent = Attachment(_make_file(b"img", "photo.bmp"), content_type="image/bmp")
    parent.save(force_insert=True)
    with (
        patch.object(parent, "preview_image", return_value=b"extracted") as preview_mock,
        patch("proper.storage.attachment.transform_image", return_value=b"thumb"),
    ):
        v = parent.variant(resize=(100, 100))
    assert preview_mock.call_args.kwargs["save"]["format"] == "png"
    assert v.filename.endswith(".png")
    assert v.content_type == "image/png"


def test_variant_explicit_save_format_overrides_default(Attachment):
    parent = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    parent.save(force_insert=True)
    with (
        patch.object(parent, "preview_image", return_value=b"extracted") as preview_mock,
        patch("proper.storage.attachment.transform_image", return_value=b"thumb"),
    ):
        v = parent.variant(resize=(100, 100), save={"format": "webp"})
    assert preview_mock.call_args.kwargs["save"]["format"] == "webp"
    assert v.filename.endswith(".webp")


def test_variant_fallback_format_is_configurable(app, Attachment):
    # Override the configured fallback for one test.
    original = app.config.get("STORAGE_FALLBACK_FORMAT")
    app.config["STORAGE_FALLBACK_FORMAT"] = "webp"
    try:
        parent = Attachment(_make_file(b"img", "photo.bmp"), content_type="image/bmp")
        parent.save(force_insert=True)
        with (
            patch.object(parent, "preview_image", return_value=b"extracted") as preview_mock,
            patch("proper.storage.attachment.transform_image", return_value=b"thumb"),
        ):
            v = parent.variant(resize=(100, 100))
    finally:
        app.config["STORAGE_FALLBACK_FORMAT"] = original
    assert preview_mock.call_args.kwargs["save"]["format"] == "webp"
    assert v.filename.endswith(".webp")


# --- Attachment.variants backref ---


def test_variants_empty_by_default(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    assert list(parent.variants) == []


def test_variants_lists_children(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v1 = parent.create_variant(_make_file(b"a", "a.txt"))
    v2 = parent.create_variant(_make_file(b"b", "b.txt"))
    variant_ids = {v.id for v in parent.variants}
    assert variant_ids == {v1.id, v2.id}


# --- Attachment.preview_image ---
# `preview_image` is the no-op extractor: an image's "extracted image" is
# the image itself, so the method just returns the source bytes. The actual
# resize/rotate/etc. pipeline runs in `variant()` via `transform_image`.


def test_preview_image_returns_source_unchanged(Attachment):
    att = Attachment(_make_file(b"img", "photo.jpg"), content_type="image/jpeg")
    att.save(force_insert=True)
    # Transformations are ignored here - they're applied by variant().
    assert att.preview_image(b"raw-bytes", resize=(100, 100)) == b"raw-bytes"


# --- Custom VARIANTS_ENABLED_FOR via subclass ---


def test_subclass_can_add_content_types(Attachment):
    class MyAttachment(Attachment):
        VARIANTS_ENABLED_FOR = {
            **Attachment.VARIANTS_ENABLED_FOR,
            "application/epub": "preview_epub",
        }

        def preview_epub(self, source, **ops):
            # Custom previewers follow the same contract as the built-in
            # ones: extract an image and return it as bytes. The transform
            # pipeline runs afterwards in variant() via transform_image.
            return b"epub-cover-png"

        class Meta:
            table_name = Attachment._meta.table_name

    parent = MyAttachment(
        _make_file(b"book", "book.epub"), content_type="application/epub"
    )
    parent.save(force_insert=True)
    with patch(
        "proper.storage.attachment.transform_image", return_value=b"epub-thumb"
    ) as transform:
        v = parent.variant(thumbnail=True)
    # variant() pipes the previewer's bytes through transform_image.
    transform.assert_called_once()
    assert transform.call_args.args[0] == b"epub-cover-png"
    assert v.download() == b"epub-thumb"


def test_custom_previewer_receives_download_and_resolved_ops(Attachment):
    # A custom previewer gets called with the source bytes and the same
    # ops dict that will later be passed to transform_image - including
    # the save format resolved by variant() from STORAGE_ALLOWED_VARIANTS /
    # STORAGE_FALLBACK_FORMAT.
    seen = {}

    class MyAttachment(Attachment):
        VARIANTS_ENABLED_FOR = {
            **Attachment.VARIANTS_ENABLED_FOR,
            "application/pdf": "preview_pdf_custom",
        }

        def preview_pdf_custom(self, source, **ops):
            seen["source"] = source
            seen["ops"] = ops
            return b"extracted-image"

        class Meta:
            table_name = Attachment._meta.table_name

    parent = MyAttachment(
        _make_file(b"pdf-data", "doc.pdf"), content_type="application/pdf"
    )
    parent.save(force_insert=True)
    with patch(
        "proper.storage.attachment.transform_image", return_value=b"processed"
    ) as transform:
        v = parent.variant(resize=(100, 100))

    assert seen["source"] == b"pdf-data"
    assert seen["ops"] == {"resize": (100, 100), "save": {"format": "png"}}
    # transform_image receives the previewer's output verbatim.
    transform.assert_called_once_with(
        b"extracted-image", resize=(100, 100), save={"format": "png"}
    )
    assert v.download() == b"processed"


# --- Attachment.preview_pdf ---


def test_preview_pdf_returns_extracted_png_bytes(Attachment):
    att = Attachment(
        _make_file(b"%PDF-stub", "doc.pdf"), content_type="application/pdf"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run") as run,
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"png-bytes"),
    ):
        result = att.preview_pdf(
            b"%PDF-stub", resize=(100, 100), save={"format": "png"}
        )

    # The previewer is now extraction-only: it returns the PNG bytes from
    # pdftoppm as-is. Resize/save ops are ignored here - variant() applies
    # them via transform_image after this returns.
    assert result == b"png-bytes"
    cmd = run.call_args.args[0]
    assert cmd[0] == "pdftoppm"
    assert "-png" in cmd
    assert "-singlefile" in cmd
    assert "-cropbox" in cmd
    assert cmd[cmd.index("-f") + 1] == "1"  # default page
    assert cmd[cmd.index("-r") + 1] == "150"  # default dpi


def test_preview_pdf_page_kwarg_passed_to_pdftoppm(Attachment):
    att = Attachment(
        _make_file(b"%PDF", "doc.pdf"), content_type="application/pdf"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run") as run,
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"png"),
    ):
        att.preview_pdf(b"%PDF", page=3)

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("-f") + 1] == "3"


def test_preview_pdf_dpi_kwarg_passed_to_pdftoppm(Attachment):
    att = Attachment(
        _make_file(b"%PDF", "doc.pdf"), content_type="application/pdf"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run") as run,
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"png"),
    ):
        att.preview_pdf(b"%PDF", dpi=300)

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("-r") + 1] == "300"


def test_preview_pdf_with_path_source_skips_tempfile(Attachment, tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-stub")
    att = Attachment(
        _make_file(b"%PDF-stub", "doc.pdf"), content_type="application/pdf"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run") as run,
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"png"),
    ):
        att.preview_pdf(str(pdf_path))

    cmd = run.call_args.args[0]
    assert cmd[1] == str(pdf_path)  # path used directly, no temp file


def test_variant_on_pdf_dispatches_to_preview_pdf(Attachment):
    Attachment.VARIANTS_ENABLED_FOR = {
        **Attachment.VARIANTS_ENABLED_FOR,
        "application/pdf": "preview_pdf",
    }
    att = Attachment(
        _make_file(b"%PDF-stub", "doc.pdf"), content_type="application/pdf"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run"),
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"page-png"),
        patch("proper.storage.attachment.transform_image", return_value=b"thumb") as transform,
    ):
        v = att.variant(resize=(200, 200))

    # variant() feeds the bytes returned by preview_pdf into transform_image
    # and injects save={"format": "png"} since PDF isn't in
    # STORAGE_ALLOWED_VARIANTS (so it falls back to STORAGE_FALLBACK_FORMAT).
    transform.assert_called_once_with(
        b"page-png", resize=(200, 200), save={"format": "png"}
    )
    assert v.download() == b"thumb"
    assert v.parent_id == att.id


# --- Attachment.preview_video ---


def test_preview_video_returns_extracted_png_bytes(Attachment):
    att = Attachment(
        _make_file(b"mp4-stub", "clip.mp4"), content_type="video/mp4"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run") as run,
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"png-bytes"),
    ):
        result = att.preview_video(
            b"mp4-stub", resize=(100, 100), save={"format": "png"}
        )

    # Extraction-only: returns the frame ffmpeg produced. Resize/save ops
    # are applied later by variant() via transform_image.
    assert result == b"png-bytes"
    cmd = run.call_args.args[0]
    assert cmd[0] == "ffmpeg"
    assert "-frames:v" in cmd
    assert cmd[cmd.index("-frames:v") + 1] == "1"
    assert cmd[cmd.index("-ss") + 1] == "1.0"  # default at_seconds


def test_preview_video_at_seconds_kwarg_passed_to_ffmpeg(Attachment):
    att = Attachment(
        _make_file(b"mp4", "clip.mp4"), content_type="video/mp4"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run") as run,
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"png"),
    ):
        att.preview_video(b"mp4", at_seconds=2.5)

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("-ss") + 1] == "2.5"


def test_preview_video_with_path_source_skips_tempfile(Attachment, tmp_path):
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"mp4-stub")
    att = Attachment(
        _make_file(b"mp4-stub", "clip.mp4"), content_type="video/mp4"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run") as run,
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"png"),
    ):
        att.preview_video(str(video_path))

    cmd = run.call_args.args[0]
    assert cmd[cmd.index("-i") + 1] == str(video_path)


def test_variant_on_video_dispatches_to_preview_video(Attachment):
    Attachment.VARIANTS_ENABLED_FOR = {
        **Attachment.VARIANTS_ENABLED_FOR,
        "video/*": "preview_video",
    }
    att = Attachment(
        _make_file(b"mp4-stub", "clip.mp4"), content_type="video/mp4"
    )
    att.save(force_insert=True)

    with (
        patch("proper.storage.attachment.subprocess.run"),
        patch("proper.storage.attachment.Path.read_bytes", return_value=b"frame-png"),
        patch("proper.storage.attachment.transform_image", return_value=b"thumb") as transform,
    ):
        v = att.variant(resize=(320, 240))

    transform.assert_called_once_with(
        b"frame-png", resize=(320, 240), save={"format": "png"}
    )
    assert v.download() == b"thumb"
    assert v.parent_id == att.id


# --- Storage.purge_variants ---


def test_purge_variants_deletes_variant_records(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    parent.create_variant(_make_file(b"a", "a.txt"))
    parent.create_variant(_make_file(b"b", "b.txt"))
    assert Attachment.select().count() == 3
    parent.purge_variants()
    assert Attachment.select().count() == 1
    assert Attachment.get_or_none(Attachment.id == parent.id)


def test_purge_variants_removes_files(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"a", "a.txt"))
    service = Attachment._get_service(v.service_name)
    path = service._get_path(v)
    assert path.exists()
    parent.purge_variants()
    assert not path.exists()


def test_purge_parent_cascades_to_variants(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    parent.create_variant(_make_file(b"a", "a.txt"))
    parent.create_variant(_make_file(b"b", "b.txt"))
    parent.purge()
    assert Attachment.select().count() == 0


def test_purge_variants_on_attachment_with_no_variants(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    parent.purge_variants()  # should not raise
    assert Attachment.select().count() == 1


# --- Storage.purge - later ---


def test_purge_later_enqueues(Attachment):
    att = Attachment(_make_file(b"x", "f.txt"))
    att.save(force_insert=True)
    service = Attachment._get_service("local")
    path = service._get_path(att)
    assert path.exists()
    assert Attachment.select().count() == 1
    att.purge_later()
    assert not path.exists()
    assert Attachment.select().count() == 0


def test_purge_variants_later_enqueues(Attachment):
    parent = Attachment(_make_file(b"x", "f.txt"))
    parent.save(force_insert=True)
    v = parent.create_variant(_make_file(b"a", "a.txt"))
    service = Attachment._get_service(v.service_name)
    path = service._get_path(v)
    assert path.exists()
    assert Attachment.select().count() == 2
    parent.purge_variants_later()
    assert not path.exists()
    assert Attachment.select().count() == 1
    assert Attachment.get_or_none(Attachment.id == parent.id) is not None


# --- DirectUpload - create_pending_blob + Disk.direct_upload_url ---


def test_create_pending_blob_writes_row_with_metadata_only(Attachment):
    att = Attachment.create_pending_blob(
        filename="My Photo.PNG",
        content_type="image/png",
        byte_size=4096,
    )

    assert att.id is not None
    assert att.pending is True
    # `parameterize` lowers + slugifies; filename comes out web-safe.
    assert att.filename == "my-photo.png"
    assert att.content_type == "image/png"
    assert att.byte_size == 4096
    # No file on disk yet - bytes arrive later via the PUT endpoint.
    assert not Attachment._get_service(att.service_name)._get_path(att).exists()


def test_create_pending_blob_infers_content_type_from_filename(Attachment):
    att = Attachment.create_pending_blob(filename="notes.md", byte_size=10)
    assert att.content_type == "text/markdown"


def test_create_pending_blob_defaults_to_octet_stream(Attachment):
    att = Attachment.create_pending_blob(filename="unknown", byte_size=1)
    assert att.content_type == DEFAULT_CONTENT_TYPE


def test_create_pending_blob_tags_source(Attachment):
    att = Attachment.create_pending_blob(
        filename="x.txt", byte_size=1, source="rich_text",
    )
    assert att.source == "rich_text"


def test_disk_direct_upload_url_targets_disk_endpoint(app, Attachment):
    att = Attachment.create_pending_blob(
        filename="x.txt", content_type="text/plain", byte_size=10,
    )
    service = Attachment._get_service(att.service_name)

    with patch.object(app, "url_for", return_value="/storage/disk/eyJ...") as mock:
        upload = service.direct_upload_url(att, checksum="abc==")

    assert upload["url"] == "/storage/disk/eyJ..."
    assert upload["headers"]["Content-Type"] == "text/plain"
    assert upload["headers"]["Content-MD5"] == "abc=="
    mock.assert_called_once()
    name, kwargs = mock.call_args[0][0], mock.call_args[1]
    assert name == "DirectUpload.update"
    assert "token" in kwargs


def test_disk_upload_token_is_salt_scoped(app, Attachment):
    """The token in `direct_upload_url` must be resolvable with
    `salt="upload"` (and only with that salt), so a leaked download
    token can't be repurposed to overwrite the bytes."""
    att = Attachment.create_pending_blob(
        filename="x.txt", content_type="text/plain", byte_size=10,
    )
    service = Attachment._get_service(att.service_name)

    # Capture the token directly without going through url_for.
    captured = {}
    original = att.generate_token
    def spy(*a, **kw):
        token = original(*a, **kw)
        captured.setdefault(kw.get("salt", "default"), token)
        return token
    att.generate_token = spy  # type: ignore[method-assign]

    with patch.object(app, "url_for", return_value="/x"):
        service.direct_upload_url(att)

    upload_token = captured["upload"]

    # The download salt (default) must reject this token.
    assert Attachment.resolve_token(upload_token, max_age=None) is None
    # The upload salt must accept it.
    resolved = Attachment.resolve_token(upload_token, max_age=None, salt="upload")
    assert resolved is not None
    assert resolved.id == att.id


def test_disk_upload_token_expires(app, Attachment, monkeypatch):
    """Upload tokens caducan en 15 min (default `resolve_token` max_age) —
    una URL filtrada no se puede reutilizar mucho después de emitirla."""
    import time

    att = Attachment.create_pending_blob(
        filename="x.txt", content_type="text/plain", byte_size=10,
    )

    captured = {}
    original = att.generate_token
    def spy(*a, **kw):
        token = original(*a, **kw)
        captured["token"] = token
        return token
    att.generate_token = spy  # type: ignore[method-assign]

    with patch.object(app, "url_for", return_value="/x"):
        Attachment._get_service(att.service_name).direct_upload_url(att)

    token = captured["token"]
    # Fresh: resolves fine.
    assert Attachment.resolve_token(token, salt="upload") is not None
    # After enough wall-clock skew, the default max_age (15 min) rejects it.
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 16 * 60)
    assert Attachment.resolve_token(token, salt="upload") is None
