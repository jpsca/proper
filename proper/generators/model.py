import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender


MODEL_BLUEPRINT = BLUEPRINTS / "model"


def gen_model(app, name, *attrs):
    """Stubs out a new model.

        ./manage.py g model NAME [column[:type[-options]][:attribute[-value]] ...]

    Arguments:

    - name: The model name (singular).
    - attrs: Optional list of columns to add to the schema.

    """
    name = inflection.singularize(name)
    class_name = inflection.camelize(name)
    snake_name = inflection.underscore(name)

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
