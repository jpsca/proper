"""Tests for proper.install.metadata — `.proper` file bookkeeping."""
import json

import pytest

from proper.install import metadata


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    app.root_path = tmp_path
    return app


def test_load_metadata_returns_empty_schema_when_file_missing(app_in_tmp):
    assert metadata.load_metadata(app_in_tmp) == {"addons": {}}


def test_is_installed_false_when_file_missing(app_in_tmp):
    assert metadata.is_installed(app_in_tmp, "storage") is False


def test_record_install_creates_file_and_entry(app_in_tmp):
    metadata.record_install(app_in_tmp, "storage", version="1.2.3")

    path = app_in_tmp.root_path / ".proper"
    assert path.exists()

    data = json.loads(path.read_text())
    assert "storage" in data["addons"]
    entry = data["addons"]["storage"]
    assert entry["version"] == "1.2.3"
    assert "installed_at" in entry
    assert entry["installed_at"].endswith("Z")
    assert "config" not in entry


def test_record_install_with_config(app_in_tmp):
    metadata.record_install(
        app_in_tmp, "storage", version="1.2.3", config={"bucket": "x"},
    )
    data = metadata.load_metadata(app_in_tmp)
    assert data["addons"]["storage"]["config"] == {"bucket": "x"}


def test_record_install_uses_current_proper_version_by_default(app_in_tmp):
    metadata.record_install(app_in_tmp, "storage")
    data = metadata.load_metadata(app_in_tmp)
    assert data["addons"]["storage"]["version"] == metadata._current_version()


def test_is_installed_after_record(app_in_tmp):
    metadata.record_install(app_in_tmp, "storage", version="1.0.0")
    assert metadata.is_installed(app_in_tmp, "storage") is True
    assert metadata.is_installed(app_in_tmp, "auth") is False


def test_record_install_upserts_does_not_duplicate(app_in_tmp):
    metadata.record_install(app_in_tmp, "storage", version="1.0.0")
    metadata.record_install(app_in_tmp, "storage", version="2.0.0")

    data = metadata.load_metadata(app_in_tmp)
    assert list(data["addons"].keys()) == ["storage"]
    assert data["addons"]["storage"]["version"] == "2.0.0"


def test_record_install_preserves_other_addons(app_in_tmp):
    metadata.record_install(app_in_tmp, "storage", version="1.0.0")
    metadata.record_install(app_in_tmp, "auth", version="1.0.0")

    data = metadata.load_metadata(app_in_tmp)
    assert set(data["addons"].keys()) == {"storage", "auth"}


def test_atomic_write_leaves_no_tmp_file(app_in_tmp):
    metadata.record_install(app_in_tmp, "storage", version="1.0.0")

    tmp_path_file = app_in_tmp.root_path / ".proper.tmp"
    assert not tmp_path_file.exists()


def test_metadata_path_helper(app_in_tmp):
    assert metadata.metadata_path(app_in_tmp) == app_in_tmp.root_path / ".proper"
