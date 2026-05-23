"""Tests for proper.install.rich_text — the rich_text addon installer.

Covers the full installer flow including the auto-install of `storage`
when it isn't yet present in the app, and the `.proper` bookkeeping.
"""
import pytest

from proper.install import metadata, rich_text


APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """An app root prepared with everything both the storage blueprint
    (in case it's auto-installed) and the rich_text blueprint expect."""
    app_root = tmp_path / APP_NAME

    for d in (
        "config", "controllers", "models",
        "tasks", "views", "assets/js", "assets/styles",
    ):
        (app_root / d).mkdir(parents=True)

    (app_root / "main.py").write_text("from proper import App\napp = App(__name__)\n")
    (app_root / "config" / "storage.py").write_text("")
    (app_root / "config" / "import_map.py").write_text("IMPORT_MAP = {\n}\n")
    (app_root / "controllers" / "__init__.py").write_text("")
    (app_root / "models" / "__init__.py").write_text("")
    (app_root / "tasks" / "__init__.py").write_text("")

    app.root_path = app_root
    app.name = APP_NAME
    return app


def test_install_renders_blueprint(app_in_tmp):
    rich_text.install(app_in_tmp)
    root = app_in_tmp.root_path

    storage_text = (root / "controllers" / "storage_controller.py").read_text()
    assert "def create(self):" in storage_text
    assert "rich_text" in storage_text

    assert (root / "views" / "rich_text_editor.jx").exists()
    assert (root / "views" / "rich_text_attachment.jx").exists()
    assert (root / "views" / "rich_text_toolbar.jx").exists()
    assert (root / "assets" / "js" / "rich-text-controller.js").exists()
    assert (root / "assets" / "js" / "vendor" / "lexxy.js").exists()
    assert (root / "assets" / "styles" / "vendor" / "lexxy.css").exists()
    assert (root / "tasks" / "rich_text_sweep.py").exists()


def test_install_records_in_proper(app_in_tmp):
    rich_text.install(app_in_tmp)
    assert metadata.is_installed(app_in_tmp, "rich_text")


def test_install_auto_installs_storage_when_missing(app_in_tmp):
    assert metadata.is_installed(app_in_tmp, "storage") is False

    rich_text.install(app_in_tmp)

    assert metadata.is_installed(app_in_tmp, "storage")
    # Storage's blueprint files landed too, so the user's Attachment
    # model is available for the rich_text controller to import.
    assert (app_in_tmp.root_path / "models" / "attachment.py").exists()


def test_install_does_not_reinstall_storage_when_already_present(app_in_tmp):
    # Pre-populate .proper as if storage were installed previously, with
    # a sentinel version we can detect surviving the rich_text install.
    metadata.record_install(app_in_tmp, "storage", version="sentinel-9.9.9")

    rich_text.install(app_in_tmp)

    # rich_text appears…
    assert metadata.is_installed(app_in_tmp, "rich_text")

    # …and storage's pre-existing entry was untouched (no re-install would
    # overwrite the version).
    data = metadata.load_metadata(app_in_tmp)
    assert data["addons"]["storage"]["version"] == "sentinel-9.9.9"

    # Storage's blueprint files were NOT rendered (the installer was skipped).
    assert not (app_in_tmp.root_path / "models" / "attachment.py").exists()


def test_install_appends_lexxy_to_import_map(app_in_tmp):
    rich_text.install(app_in_tmp)
    text = (app_in_tmp.root_path / "config" / "import_map.py").read_text()
    assert '"lexxy"' in text


def test_install_wires_controller_and_task_into_their_inits(app_in_tmp):
    rich_text.install(app_in_tmp)
    root = app_in_tmp.root_path

    controllers_init = (root / "controllers" / "__init__.py").read_text()
    assert "from . import rich_text_controller" in controllers_init

    tasks_init = (root / "tasks" / "__init__.py").read_text()
    assert "from . import rich_text_sweep" in tasks_init
