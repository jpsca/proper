from ..helpers.render import BLUEPRINTS, BlueprintRender, call, sort_imports


STORAGE_BLUEPRINT = BLUEPRINTS / "storage"
CONFIG_PATH = "config/application.py"


def install(app, migration=False):
    """Install storage support for uploaded files.
    Use `--migration` to generate a migration for creating
    the supporting tables.
    """
    pass

    bp = BlueprintRender(
        STORAGE_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
        },
        ignore=[],
    )
    bp()

    config_path = app.root_path / CONFIG_PATH
    code = sort_imports(config_path.read_text())
    config_path.write_text(code)

    if migration:
        call('proper db revision "Create storage tables"')
