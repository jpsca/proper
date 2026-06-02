"""Tests for proper.install.storage - installs storage blueprint into an app."""

import pytest

from proper import metadata, storage


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the files that the storage blueprint
    expects to already exist."""
    app_root = tmp_path / "myapp"

    for d in ("config", "controllers", "models"):
        (app_root / d).mkdir(parents=True)

    (app_root / "config" / "storage.py").write_text("")
    (app_root / "main.py").write_text("from proper import App\napp = App(__name__)\n")
    (app_root / "models" / "__init__.py").write_text("")

    app.root_path = app_root
    app.name = "myapp"
    return app


def test_file_creation(app_in_tmp):
    storage.install(app_in_tmp)

    # creates_storage_controller
    path = app_in_tmp.root_path / "controllers" / "storage_controller.py"
    assert path.exists()

    # creates_attachment_model
    path = app_in_tmp.root_path / "models" / "attachment.py"
    assert path.exists()

    # main.py is left alone - the new shape doesn't need an app.storage alias
    text = (app_in_tmp.root_path / "main.py").read_text()
    assert "storage = app.storage" not in text

    # appends_storage_config
    text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
    assert "STORAGE_SERVICES" in text
    assert "STORAGE =" in text

    # appends_to_models_init
    text = (app_in_tmp.root_path / "models" / "__init__.py").read_text()
    assert "from .attachment import Attachment" in text

    # config_has_local_service
    text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
    assert '"local"' in text
    assert '"Disk"' in text

    # config_has_test_service
    text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
    assert '"test"' in text

    # config_has_amazon_service
    text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
    assert '"amazon"' in text
    assert '"S3"' in text

    # config_has_web_image_content_types
    text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
    assert "STORAGE_ALLOWED_VARIANTS" in text

    # config_has_allowed_inline
    text = (app_in_tmp.root_path / "config" / "storage.py").read_text()
    assert "STORAGE_ALLOWED_INLINE" in text

    # records the install in .proper
    assert metadata.is_installed(app_in_tmp, "storage")
