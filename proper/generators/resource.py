

ROUTES_TMPL = """,
    resource("[[ action ]]", to="[[ pascal_name ]]"),
]

"""


def resource(app, name):
    """Stubs out a new resource.

    This include a model, controller, templates, and
    a resource route in the `routes.py` file

    Arguments:

    - name: PascalCased name of the resource class

    """
    pass
