import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender, append_routes
from proper.router.resource import ACTIONS

from .model import gen_model


RESOURCE_BLUEPRINT = BLUEPRINTS / "resource"
ROUTES_TMPL = "routes.py.tmpl"


def gen_resource(app, name, *attrs, only=None, ignore=None, singular=False):
    """Stubs out a new resource.

    This include a model, controller, templates, and a resource
    route in the `routes.py` file

    Pass the resource name, an optional list of attribute pairs
    as arguments, and options.

    Attribute pairs are field:type arguments specifying the model's attributes,
    and follows the same syntax of the model generator.
    Run `bin/manage g model --help` for instructions.

    You don't have to think up every attribute up front, but it helps to
    sketch out a few so you can start working with the model immediately.

    By default it generates the full set of REST actions, but you can choose
    only some of these or to ignore a few by using the optional `only` and
    `ignore` arguments.

    Sometimes, you have a resource that clients always look up without referencing an ID.
    In this case, you can use `singular=True` to build a set of REST routes without `:uid`.

    Examples:

        bin/manage g resource post
        bin/manage g resource post --only
        bin/manage g resource post title:string body:text published:boolean
        bin/manage g resource --singular

    """
    snake_name = inflection.underscore(name)

    gen_model(app, name, *attrs)

    actions = set(ACTIONS)
    if only:
        actions = actions.intersection(set(only))
    elif ignore:
        actions = actions.difference(set(ignore))
    if singular:
        actions.remove("index")

    ignored_templates = [
        f"{action}.html.jinja"
        for action in set(ACTIONS).difference(actions)
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
        ignore=[ROUTES_TMPL] + ignored_templates
    )
    bp()

    routes_tmpl = RESOURCE_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)
