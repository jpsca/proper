import pytest

from proper import metadata, rich_text
from proper.rich_text import sanitizer


APP_NAME = "myapp"


@pytest.fixture(autouse=True)
def commands(monkeypatch):
    """The commands that the installer would run, like the one that adds
    the dependencies. They are recorded instead of run."""
    commands = []
    monkeypatch.setattr("proper.helpers.render.call", commands.append)
    return commands


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """A minimal app root with the directories the blueprint expects to
    already exist (controllers/, tasks/, config/).
    """
    app_root = tmp_path / APP_NAME

    for d in ("controllers", "tasks", "config", "views", "assets/js", "assets/css"):
        (app_root / d).mkdir(parents=True)

    (app_root / "controllers" / "__init__.py").write_text("")
    (app_root / "tasks" / "__init__.py").write_text("")
    (app_root / "config" / "__init__.py").write_text("")
    (app_root / "config" / "import_map.py").write_text(
        "IMPORT_MAP = {\n}\n"
    )

    app.root_path = app_root
    app.name = APP_NAME
    return app


def test_install_renders_blueprint(app_in_tmp):
    rich_text.install(app_in_tmp)
    root = app_in_tmp.root_path

    # The DirectUpload create endpoint ships from the storage blueprint;
    # rich_text doesn't append anything to the controller anymore — it
    # just ships the editor views, JS, vendored assets, and the sweep.
    storage_text = (root / "controllers" / "storage_controller.py").read_text()
    assert "def create(self):" in storage_text

    assert (root / "views" / "rich_text_editor.jx").exists()
    assert (root / "views" / "rich_text_attachment.jx").exists()
    assert (root / "views" / "rich_text_toolbar.jx").exists()
    assert (root / "assets" / "js" / "lexxy-config.js").exists()
    assert (root / "assets" / "js" / "vendor" / "lexxy.js").exists()
    assert (root / "assets" / "css" / "lexxy-editor.css").exists()
    assert (root / "assets" / "css" / "lexxy-content.css").exists()
    assert (root / "tasks" / "abandoned_uploads_sweep.py").exists()


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


def test_install_wires_sweep_task_into_init(app_in_tmp):
    rich_text.install(app_in_tmp)
    tasks_init = (app_in_tmp.root_path / "tasks" / "__init__.py").read_text()
    assert "from . import abandoned_uploads_sweep" in tasks_init


def test_install_adds_the_config_of_the_sanitizer(app_in_tmp):
    rich_text.install(app_in_tmp)
    config = app_in_tmp.root_path / "config"

    assert "from .rich_text import *" in (config / "__init__.py").read_text()

    settings: dict = {}
    exec((config / "rich_text.py").read_text(), settings)  # noqa: S102
    assert settings["RICH_TEXT_SANITIZE"] is True
    # The config that is installed is the default of the sanitizer
    assert tuple(settings["RICH_TEXT_ALLOWED_TAGS"]) == sanitizer.ALLOWED_TAGS
    assert {
        tag: tuple(names) for tag, names in settings["RICH_TEXT_ALLOWED_ATTRIBUTES"].items()
    } == sanitizer.ALLOWED_ATTRIBUTES
    assert tuple(settings["RICH_TEXT_ALLOWED_STYLES"]) == sanitizer.ALLOWED_STYLES
    assert tuple(settings["RICH_TEXT_ALLOWED_URL_SCHEMES"]) == sanitizer.ALLOWED_URL_SCHEMES


def test_install_adds_the_dependency_of_the_sanitizer(app_in_tmp, commands):
    rich_text.install(app_in_tmp)
    assert 'pip install "nh3"' in commands


def test_install_adds_the_dependency_with_uv(app_in_tmp, commands):
    (app_in_tmp.root_path.parent / "uv.lock").write_text("")
    rich_text.install(app_in_tmp)
    assert 'uv add "nh3"' in commands
