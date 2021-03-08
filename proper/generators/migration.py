from datetime import datetime

import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender


MIGRATION_BLUEPRINT = BLUEPRINTS / "migration"


def gen_migration(app, name, table=None, create=False):
    """Create a new migration file.

        bin/manage g migration NAME [--table table_name] [--create]

    Arguments:

    - name: The name of the migration.
    - table: The table to create the migration for.
    - create : Whether the migration will create the table or not.

    """
    name = name.replace(" ", "_")
    class_name = inflection.camelize(name)
    table = inflection.pluralize(table) if table else None
    snake_name = inflection.underscore(name)

    bp = BlueprintRender(
        MIGRATION_BLUEPRINT,
        app.root_path.parent,
        context={
            "snake_name": snake_name,
            "class_name": class_name,
            "table": table,
            "create": create,
            "dt": get_dt_slug(),
        },
    )
    bp()


def get_dt_slug():
    return (
        str(datetime.utcnow())
        .split(".")[0]
        .replace("-", "_")
        .replace("T", "_")
        .replace(" ", "_")
        .replace(":", "")
    )
