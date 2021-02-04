from proper.helpers import BLUEPRINTS, BlueprintRender, extend_routes, pascal_to_snake


ROUTES_TMPL = """,[% for action in actions %]
    get("[[ action ]]", to="[[ pascal_name ]].[[ action ]]"),[% endfor %]
]

"""


def controller(app, name, *actions):
    """Stubs out a new controller and its templates.

        bin/manage g controller NAME [action ...]

    Pass the PascalCased controller name (in plural), and an optional list
    of actions as arguments.
    Example:

        bin/manage g controller Articles index show

    """
    snake_name = pascal_to_snake(name)
    actions = [pascal_to_snake(action) for action in actions]

    bprender = BlueprintRender(
        BLUEPRINTS / "controller",
        app.root_path,
        context={
            "pascal_name": name,
            "snake_name": snake_name,
            "actions": actions or ["index"],
        },
    )
    bprender()

    new_routes = bprender.string(ROUTES_TMPL)
    extend_routes(app, new_routes)

    templates = app.root_path / "templates" / snake_name
    templates.mkdir(parents=False, exist_ok=True)
    _stub_templates(templates, actions)


def _stub_templates(path, actions):
    source = (BLUEPRINTS / "template.html.jinja").read_text()
    for action in actions:
        action = action.lower()
        (path / f"{action}.html.jinja").write_text(source)
