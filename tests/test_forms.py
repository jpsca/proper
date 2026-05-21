"""Tests for proper.forms"""

import typing as t
from io import BytesIO

import pytest

from proper.forms import AttachmentField, errors


# ── helpers ─────────────────────────────────────────────────────────


class FakeAttachment:
    """Stand-in for the runtime Attachment class. Validation never builds
    instances - it only uses `attachment_cls` for `isinstance` checks in
    `set()`/`save()`, which these tests don't exercise.
    """


# `AttachmentField.__init__` types `attachment_cls` as `type[TAttachment]`,
# a TYPE_CHECKING-only protocol; cast so the test's lightweight stand-in
# satisfies the static type without a runtime subclass.
FAKE_ATTACHMENT: t.Any = FakeAttachment


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


# ── max_size ────────────────────────────────────────────────────────


def test_max_size_passes_when_under_limit():
    field = AttachmentField(FAKE_ATTACHMENT, max_size=1024, required=False)
    _bind(field, _make_upload(size=500))
    assert field.validate() is True
    assert field.error is None


def test_max_size_passes_at_exact_boundary():
    """`size > max_size` is the failure condition - equality must pass."""
    field = AttachmentField(FAKE_ATTACHMENT, max_size=1024, required=False)
    _bind(field, _make_upload(size=1024))
    assert field.validate() is True
    assert field.error is None


def test_max_size_fails_when_over_limit():
    field = AttachmentField(FAKE_ATTACHMENT, max_size=1024, required=False)
    _bind(field, _make_upload(size=2048))
    assert field.validate() is False
    assert field.error == errors.FILE_TOO_LARGE


def test_max_size_error_args_use_format_size():
    """`max_size` is rendered through `format_size` so message templates
    can interpolate a human-readable value (e.g. `'1 KB'`).
    """
    field = AttachmentField(FAKE_ATTACHMENT, max_size=1024, required=False)
    _bind(field, _make_upload(size=2048))
    field.validate()
    assert field.error_args == {"max_size": "1 KB"}


def test_max_size_skipped_when_size_attr_missing():
    """A bound `Attachment` (manual assignment, not an upload) has no
    `size` attribute - validation must not fail in that case.
    """
    field = AttachmentField(FAKE_ATTACHMENT, max_size=1024, required=False)
    upload = _make_upload()  # no `size` attribute set
    _bind(field, upload)
    assert field.validate() is True
    assert field.error is None


def test_max_size_none_disables_check():
    field = AttachmentField(FAKE_ATTACHMENT, max_size=None, required=False)
    _bind(field, _make_upload(size=10**12))
    assert field.validate() is True


# ── accept ──────────────────────────────────────────────────────────


def test_accept_allows_glob_match():
    """`image/*` matches any subtype under `image/`."""
    field = AttachmentField(FAKE_ATTACHMENT, accept=["image/*"], required=False)
    _bind(field, _make_upload(content_type="image/png"))
    assert field.validate() is True
    assert field.error is None


def test_accept_allows_each_subtype_under_a_glob():
    field = AttachmentField(FAKE_ATTACHMENT, accept=["image/*"], required=False)
    _bind(field, _make_upload(content_type="image/jpeg"))
    assert field.validate() is True


def test_accept_allows_exact_pattern():
    """A pattern without wildcards matches the literal content type."""
    field = AttachmentField(
        FAKE_ATTACHMENT, accept=["application/pdf"], required=False
    )
    _bind(field, _make_upload(content_type="application/pdf"))
    assert field.validate() is True


def test_accept_rejects_non_matching():
    field = AttachmentField(FAKE_ATTACHMENT, accept=["image/*"], required=False)
    _bind(field, _make_upload(content_type="application/pdf"))
    assert field.validate() is False
    assert field.error == errors.INVALID_CONTENT_TYPE
    assert field.error_args == {"accept": ["image/*"]}


def test_accept_rejects_substring_without_wildcard():
    """`image/` (no wildcard) is a literal pattern - `image/png` doesn't match.
    Glob matching, not prefix matching.
    """
    field = AttachmentField(FAKE_ATTACHMENT, accept=["image/"], required=False)
    _bind(field, _make_upload(content_type="image/png"))
    assert field.validate() is False
    assert field.error == errors.INVALID_CONTENT_TYPE


def test_accept_accepts_any_listed_pattern():
    field = AttachmentField(
        FAKE_ATTACHMENT,
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
    field = AttachmentField(FAKE_ATTACHMENT, accept=["IMAGE/*"], required=False)
    _bind(field, _make_upload(content_type="image/PNG"))
    assert field.validate() is True


def test_accept_skipped_when_attr_missing():
    field = AttachmentField(FAKE_ATTACHMENT, accept=["image/*"], required=False)
    upload = _make_upload()  # no `content_type` set
    _bind(field, upload)
    assert field.validate() is True


def test_accept_none_disables_check():
    field = AttachmentField(FAKE_ATTACHMENT, accept=None, required=False)
    _bind(field, _make_upload(content_type="application/x-msdownload"))
    assert field.validate() is True


def test_accept_empty_list_disables_check():
    """An empty list is treated as 'no patterns configured', same as None."""
    field = AttachmentField(FAKE_ATTACHMENT, accept=[], required=False)
    _bind(field, _make_upload(content_type="application/x-msdownload"))
    assert field.validate() is True


# ── combined ────────────────────────────────────────────────────────


def test_both_rules_pass_together():
    field = AttachmentField(
        FAKE_ATTACHMENT,
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
        FAKE_ATTACHMENT,
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
        FAKE_ATTACHMENT,
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
    field = AttachmentField(FAKE_ATTACHMENT, max_size=raw_size, required=False)
    _bind(field, _make_upload(size=raw_size + 1))
    field.validate()
    assert field.error_args == {"max_size": expected}
