"""Tests for the rich_text blueprint files.

Exercises `render_blueprint` directly (not via the installer, which lives
in stage 7) so we know the blueprint produces the expected file layout
and that template substitution lands cleanly.
"""
import pytest

from proper.helpers import BLUEPRINTS
from proper.helpers.render import render_blueprint


APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """A minimal app root with the directories the blueprint expects to
    already exist (controllers/, tasks/, config/).
    """
    app_root = tmp_path / APP_NAME

    for d in ("controllers", "tasks", "config", "views", "assets/js", "assets/styles"):
        (app_root / d).mkdir(parents=True)

    (app_root / "controllers" / "__init__.py").write_text("")
    (app_root / "tasks" / "__init__.py").write_text("")
    (app_root / "config" / "import_map.py").write_text(
        "IMPORT_MAP = {\n}\n"
    )

    app.root_path = app_root
    app.name = APP_NAME
    return app


def test_blueprint_renders_all_files(app_in_tmp):
    render_blueprint(
        BLUEPRINTS / "rich_text",
        app_in_tmp.root_path.parent,
        context={"app_name": app_in_tmp.name},
    )
    root = app_in_tmp.root_path

    # Upload action appended to the storage addon's controller
    storage_text = (root / "controllers" / "storage_controller.py").read_text()
    assert "def create(self):" in storage_text
    assert "source=\"rich_text\"" in storage_text
    assert APP_NAME in storage_text  # template substitution worked
    assert "[[app_name]]" not in storage_text

    # Jx components
    assert (root / "views" / "rich_text_editor.jx").exists()
    assert (root / "views" / "rich_text_attachment.jx").exists()
    assert (root / "views" / "rich_text_toolbar.jx").exists()

    # Stimulus controller
    assert (root / "assets" / "js" / "rich-text-controller.js").exists()

    # Vendored Lexxy JS bundle + stylesheets land in the user's app
    js_vendor = root / "assets" / "js" / "vendor"
    assert (js_vendor / "lexxy.js").exists()

    css_vendor = root / "assets" / "styles" / "vendor"
    assert (css_vendor / "lexxy.css").exists()

    # Periodic sweep task
    sweep = root / "tasks" / "rich_text_sweep.py"
    assert sweep.exists()
    sweep_text = sweep.read_text()
    assert "purge_abandoned_uploads" in sweep_text
    assert APP_NAME in sweep_text
    assert "[[app_name]]" not in sweep_text

    # tasks/__init__ append wires up the sweep
    tasks_init = (root / "tasks" / "__init__.py").read_text()
    assert "from . import rich_text_sweep" in tasks_init

    # IMPORT_MAP append registers the Lexxy bare specifier
    import_map_text = (root / "config" / "import_map.py").read_text()
    assert '"lexxy"' in import_map_text
