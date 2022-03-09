from pathlib import Path

from proper.helpers.render import BLUEPRINTS, BlueprintRender, append_routes


AUTH_BLUEPRINT = BLUEPRINTS / "proper_auth"
ROUTES_TMPL = "routes.tmpl.py"


def install(app):
    """
    """
    root_path = Path(app.root_path.parent)

    bp = BlueprintRender(
        AUTH_BLUEPRINT,
        root_path,
        context={"app_name": app.root_path.name, },
        ignore=[ROUTES_TMPL, ]
    )
    bp()

    routes_tmpl = AUTH_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)
