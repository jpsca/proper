from ..helpers.render import BLUEPRINTS, BlueprintRender, call


STORAGE_BLUEPRINT = BLUEPRINTS / "storage"


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

    if migration:
        call('proper db revision "Create storage tables"')
