import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender, append_routes
from proper.router.resource import ACTIONS
from .model import gen_model


RESOURCE_BLUEPRINT = BLUEPRINTS / "resource"
ROUTES_TMPL = "routes.tmpl.py"


def gen_resource(app, name, *attrs, only=None, ignore=None, singular=False):
    """Stubs out a new resource
    including a controller, model, migration, templates, and a resource route
    in the `routes.py` file

        ./manage.py g resource NAME
            [--only=action[,action]] [--ignore=action[,action]] [--singular]

    Arguments:

    - name: The model name (singular).
    - only: Optional comma-separated list of actions to include,
        instead of using the full set.)
    - ignore: Optional comma-separated lists of actions to NOT include
        from the full set of actions.
    - singular [False]: Wether the resource is just one.
    - attrs: Optional list of columns to add to the schema of the resource.

    Attribute pairs are field:type arguments specifying the model's attributes,
    and follows the same syntax of the model generator.
    Run `./manage.py g model --help` for instructions.

    By default it generates the full set of REST actions, but you can choose
    only some of these or to ignore a few by using the optional `only` and
    `ignore` arguments.

    Sometimes, you have a resource that clients always look up without
    referencing an ID. In this case, you can use `singular=True` to build a
    set of REST routes without `:uid`.

    Examples:

        ./manage.py g resource post
        ./manage.py g resource post --only=index,show
        ./manage.py g resource post title:string body:text published:boolean
        ./manage.py g resource --singular

    """
    snake_name = inflection.underscore(name)

    actions = set(ACTIONS)
    if only:
        actions = actions.intersection(set(only.split(",")))
    elif ignore:
        actions = actions.difference(set(ignore.split(",")))
    if singular:
        actions.remove("index")

    ignored_templates = [
        f"{action}.html.jinja" for action in set(ACTIONS).difference(actions)
    ]
    bp = BlueprintRender(
        RESOURCE_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
            "snake_name": snake_name,
            "class_name": name,
            "actions": actions,
            "singular": singular,
        },
        ignore=[ROUTES_TMPL] + ignored_templates,
    )
    bp()

    gen_model(app, name, *attrs)

    routes_tmpl = RESOURCE_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)
