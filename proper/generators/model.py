import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender
from .migration import SCHEMA_GEN_DOC, gen_migration


MODEL_BLUEPRINT = BLUEPRINTS / "model"


def gen_model(app, name, *attrs):
    name = inflection.singularize(name)
    class_name = inflection.camelize(name)
    snake_name = inflection.underscore(name)
    table_name = inflection.tableize(class_name)

    bp = BlueprintRender(
        MODEL_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
            "class_name": class_name,
            "snake_name": snake_name,
        },
    )
    bp()

    gen_migration(app, f"create {table_name}", table=table_name, create=True, *attrs)


gen_model.__doc__ = """Stubs out a new model and generates a migration
to create the table for that model.

    bin/manage g model NAME [column[:type[-options]][:attribute[-value]] ...]

Arguments:

- name: The model name (singular).
- attrs: Optional list of columns to add to the schema.

""" + SCHEMA_GEN_DOC.format(
    cmd="model Product"
)
