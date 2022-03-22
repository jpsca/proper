from pathlib import Path

from ..helpers.render import BLUEPRINTS, BlueprintRender, append_routes


AUTH_BLUEPRINT = BLUEPRINTS / "auth"
ROUTES_TMPL = "routes.tmpl.py"
APPLICATION_CONTROLLER = "controllers/application.py"

REPLACE_PRE = "\n\nclass AppController("
WITH_PRE = """from .concerns import LoadUser, RequireLogin
\n\nclass AppController(LoadUser, """
FALLBACK = """from proper import Controller, response
from .concerns import LoadUser, RequireLogin
\n\nclass AppController(LoadUser, Controller):
"""


def install(app):
    """Install user/password authentication support."""
    root_path = Path(app.root_path.parent)

    bp = BlueprintRender(
        AUTH_BLUEPRINT,
        root_path,
        context={},
        ignore=[ROUTES_TMPL],
    )
    bp()

    curr_appc = root_path / APPLICATION_CONTROLLER
    if not curr_appc.is_file():
        raise ValueError(f"{str(curr_appc)} not found")
    text = curr_appc.read_text()
    if REPLACE_PRE in text:
        text = text.replace(REPLACE_PRE, WITH_PRE)
    else:
        text = f"{FALLBACK}{text}"
    curr_appc.write_text(text)

    routes_tmpl = AUTH_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)
