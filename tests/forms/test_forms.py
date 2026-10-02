from io import BytesIO
from pathlib import Path

import pytest

import proper
from proper.core.request.formparser import MultipartPart
from proper.forms import AttachmentField, errors
from proper.storage import _Attachment


# --- Helpers ---


class FakeAttachment(_Attachment):
    """Stand-in for the runtime Attachment class. Validation never builds
    instances - it only uses `attachment_cls` for `isinstance` checks in
    `set()`/`save()`, which these tests don't exercise.
    """


def _make_upload(*, filename="test.bin", size=None, content_type=None):
    """Build a stand-in for `MultipartPart`: a file-like object with the
    same duck-typed attrs `validate_value` reads (`filename`, `size`,
    `content_type`).
    """
    buf = BytesIO(b"")
    buf.filename = filename  # type: ignore
    if size is not None:
        buf.size = size  # type: ignore
    if content_type is not None:
        buf.content_type = content_type  # type: ignore
    return buf


def _bind(field, upload):
    """Run an upload through `set()` so `validate()` sees the same state
    a real form submission would produce.
    """
    field.set({"file": upload})


# --- max_size ---


def test_max_size_passes_when_under_limit():
    field = AttachmentField(FakeAttachment, max_size=1024, required=False)
    _bind(field, _make_upload(size=500))
    assert field.validate() is True
    assert field.error is None


def test_max_size_passes_at_exact_boundary():
    """`size > max_size` is the failure condition - equality must pass."""
    field = AttachmentField(FakeAttachment, max_size=1024, required=False)
    _bind(field, _make_upload(size=1024))
    assert field.validate() is True
    assert field.error is None


def test_max_size_fails_when_over_limit():
    field = AttachmentField(FakeAttachment, max_size=1024, required=False)
    _bind(field, _make_upload(size=2048))
    assert field.validate() is False
    assert field.error == errors.FILE_TOO_LARGE


def test_max_size_error_args_use_format_size():
    """`max_size` is rendered through `format_size` so message templates
    can interpolate a human-readable value (e.g. `'1 KB'`).
    """
    field = AttachmentField(FakeAttachment, max_size=1024, required=False)
    _bind(field, _make_upload(size=2048))
    field.validate()
    assert field.error_args == {"max_size": "1 KB"}


def test_max_size_skipped_when_size_attr_missing():
    """A bound `Attachment` (manual assignment, not an upload) has no
    `size` attribute - validation must not fail in that case.
    """
    field = AttachmentField(FakeAttachment, max_size=1024, required=False)
    upload = _make_upload()  # no `size` attribute set
    _bind(field, upload)
    assert field.validate() is True
    assert field.error is None


def test_max_size_none_disables_check():
    field = AttachmentField(FakeAttachment, max_size=None, required=False)
    _bind(field, _make_upload(size=10**12))
    assert field.validate() is True


# --- accept ---


def test_accept_allows_glob_match():
    """`image/*` matches any subtype under `image/`."""
    field = AttachmentField(FakeAttachment, accept=["image/*"], required=False)
    _bind(field, _make_upload(content_type="image/png"))
    assert field.validate() is True
    assert field.error is None


def test_accept_allows_each_subtype_under_a_glob():
    field = AttachmentField(FakeAttachment, accept=["image/*"], required=False)
    _bind(field, _make_upload(content_type="image/jpeg"))
    assert field.validate() is True


def test_accept_allows_exact_pattern():
    """A pattern without wildcards matches the literal content type."""
    field = AttachmentField(
        FakeAttachment, accept=["application/pdf"], required=False
    )
    _bind(field, _make_upload(content_type="application/pdf"))
    assert field.validate() is True


def test_accept_rejects_non_matching():
    field = AttachmentField(FakeAttachment, accept=["image/*"], required=False)
    _bind(field, _make_upload(content_type="application/pdf"))
    assert field.validate() is False
    assert field.error == errors.INVALID_CONTENT_TYPE
    assert field.error_args == {"accept": ["image/*"]}


def test_accept_rejects_substring_without_wildcard():
    """`image/` (no wildcard) is a literal pattern - `image/png` doesn't match.
    Glob matching, not prefix matching.
    """
    field = AttachmentField(FakeAttachment, accept=["image/"], required=False)
    _bind(field, _make_upload(content_type="image/png"))
    assert field.validate() is False
    assert field.error == errors.INVALID_CONTENT_TYPE


def test_accept_accepts_any_listed_pattern():
    field = AttachmentField(
        FakeAttachment,
        accept=["image/*", "application/pdf"],
        required=False,
    )
    _bind(field, _make_upload(content_type="application/pdf"))
    assert field.validate() is True
    _bind(field, _make_upload(content_type="image/gif"))
    assert field.validate() is True


def test_accept_is_case_insensitive():
    """Both the patterns and the upload's content_type are lowercased
    before matching, so `IMAGE/PNG` matches `image/*`.
    """
    field = AttachmentField(FakeAttachment, accept=["IMAGE/*"], required=False)
    _bind(field, _make_upload(content_type="image/PNG"))
    assert field.validate() is True


def test_accept_skipped_when_attr_missing():
    field = AttachmentField(FakeAttachment, accept=["image/*"], required=False)
    upload = _make_upload()  # no `content_type` set
    _bind(field, upload)
    assert field.validate() is True


def test_accept_none_disables_check():
    field = AttachmentField(FakeAttachment, accept=None, required=False)
    _bind(field, _make_upload(content_type="application/x-msdownload"))
    assert field.validate() is True


def test_accept_empty_list_disables_check():
    """An empty list is treated as 'no patterns configured', same as None."""
    field = AttachmentField(FakeAttachment, accept=[], required=False)
    _bind(field, _make_upload(content_type="application/x-msdownload"))
    assert field.validate() is True


# --- combined ---


def test_both_rules_pass_together():
    field = AttachmentField(
        FakeAttachment,
        max_size=1024,
        accept=["image/*"],
        required=False,
    )
    _bind(field, _make_upload(size=500, content_type="image/png"))
    assert field.validate() is True


def test_max_size_reported_first_when_both_fail():
    """`max_size` is checked before `accept`; if both fail, the
    size error is the one surfaced.
    """
    field = AttachmentField(
        FakeAttachment,
        max_size=1024,
        accept=["image/*"],
        required=False,
    )
    _bind(field, _make_upload(size=2048, content_type="application/pdf"))
    assert field.validate() is False
    assert field.error == errors.FILE_TOO_LARGE


def test_validate_noop_when_value_is_none():
    """No upload + not required → nothing to validate."""
    field = AttachmentField(
        FakeAttachment,
        max_size=1024,
        accept=["image/*"],
        required=False,
    )
    field.set({"file": None})
    assert field.validate() is True


@pytest.mark.parametrize(
    "raw_size, expected",
    [
        (1024, "1 KB"),
        (1024 * 1024, "1 MB"),
        (500, "500 Bytes"),
    ],
)
def test_max_size_args_round_trip_through_format_size(raw_size, expected):
    field = AttachmentField(FakeAttachment, max_size=raw_size, required=False)
    _bind(field, _make_upload(size=raw_size + 1))
    field.validate()
    assert field.error_args == {"max_size": expected}


# --- The saved attachment, and the components that show it ---


VIEWS = Path(proper.__file__).parent / "_blueprints" / "addon_storage" / "[[app_name]]" / "views"


def test_attachment_is_the_saved_one():
    saved = FakeAttachment()
    field = AttachmentField(FakeAttachment)
    field.set(None, saved)
    assert field.attachment is saved


def test_attachment_is_none_without_a_value():
    field = AttachmentField(FakeAttachment, required=False)
    field.set(None)
    assert field.attachment is None


def test_attachment_is_none_for_an_upload():
    field = AttachmentField(FakeAttachment)
    field.set({"file": _make_upload(filename="photo.png")}, FakeAttachment())
    assert field.attachment is None


def test_attachment_is_none_when_removed():
    field = AttachmentField(FakeAttachment, required=False)
    field.set({"_destroy": "1"}, FakeAttachment())
    assert field.attachment is None


@pytest.mark.parametrize("component", ["image_input.jx", "file_input.jx"])
def test_component_with_an_upload_that_did_not_validate(app, component):
    """Regression: the components asked the upload for its `url`,
    and the form failed instead of showing the error."""
    app.catalog.add_folder(VIEWS)
    field = AttachmentField(FakeAttachment, max_size=10)
    field.field_name = "photo"
    upload = MultipartPart()
    upload.filename = "big.png"
    upload.content_type = "image/png"
    upload.size = 100
    field.set({"file": upload})
    assert field.validate_value() is False

    html = str(app.catalog.render(component, field=field))

    assert 'name="photo[file]"' in html
    # The component is not marked as having a file
    assert '<div class="image-input"' in html or '<div class="file-input"' in html
    assert "File size should be 10 Bytes or less" in html


@pytest.mark.parametrize("component", ["image_input.jx", "file_input.jx"])
def test_component_without_a_value(app, component):
    app.catalog.add_folder(VIEWS)
    field = AttachmentField(FakeAttachment, required=False)
    field.field_name = "photo"
    field.set(None)

    html = str(app.catalog.render(component, field=field))

    assert 'name="photo[file]"' in html
    assert 'name="photo[_destroy]"' in html
