"""Tests for proper.install.storage — installs storage blueprint into an app."""

import pytest

from proper.install.storage import SORT_IMPORTS_IN, install


APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the files that the storage blueprint
    expects to already exist."""
    app_root = tmp_path / APP_NAME

    for d in ("config", "controllers", "models"):
        (app_root / d).mkdir(parents=True)

    (app_root / "config" / "storage.py").write_text("")
    (app_root / "main.py").write_text("from proper import App\napp = App(__name__)\n")
    (app_root / "models" / "__init__.py").write_text("")

    app.root_path = app_root
    app.name = APP_NAME
    return app


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------


class TestFileCreation:
    def test_creates_storage_controller(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "controllers" / "storage_controller.py"
        assert path.exists()

    def test_creates_attachment_model(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "models" / "attachment.py"
        assert path.exists()


# ---------------------------------------------------------------------------
# Appended content
# ---------------------------------------------------------------------------


class TestAppendedContent:
    def test_appends_to_main(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "main.py").read_text()
        assert "storage = app.storage" in text

    def test_appends_storage_config(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
        assert "STORAGE_SERVICES" in text
        assert "STORAGE =" in text

    def test_appends_to_models_init(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "models" / "__init__.py").read_text()
        assert "from .attachment import Attachment" in text


# ---------------------------------------------------------------------------
# Storage config content
# ---------------------------------------------------------------------------


class TestStorageConfig:
    def test_config_has_local_service(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
        assert '"local"' in text
        assert '"Disk"' in text

    def test_config_has_test_service(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
        assert '"test"' in text

    def test_config_has_amazon_service(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
        assert '"amazon"' in text
        assert '"S3"' in text

    def test_config_has_web_image_content_types(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
        assert "STORAGE_WEB_IMAGE_CONTENT_TYPES" in text

    def test_config_has_allowed_inline_content_types(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
        assert "STORAGE_ALLOWED_INLINE_CONTENT_TYPES" in text


# ---------------------------------------------------------------------------
# sort_imports_in
# ---------------------------------------------------------------------------


class TestSortImports:
    def test_sort_imports_targets(self):
        assert "config/storage.py" in SORT_IMPORTS_IN
