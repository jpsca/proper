from proper.helpers.render import BLUEPRINTS


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
ROUTES_TMPL = BLUEPRINTS / "routes.py.resource.tmpl"
TEMPLATE_TMPL = BLUEPRINTS / "template.html.jinja.tmpl"


def gen_resource(app, name, *attrs, *, only=None, ignore=None, singular=False):
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
    pass
