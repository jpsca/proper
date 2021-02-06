from proper.helpers.render import BLUEPRINTS


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
ROUTES_TMPL = BLUEPRINTS / "routes.py.resource.tmpl"
TEMPLATE_TMPL = BLUEPRINTS / "template.html.jinja.tmpl"


def gen_resource(app, name, only=None, ignore=None, singular=False):
    """Stubs out a new resource.

    This include a model, controller, templates, and
    a resource route in the `routes.py` file

    Arguments:

    - name: PascalCased name of the resource class

    """
    pass
