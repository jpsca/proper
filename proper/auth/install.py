from ..helpers.render import BLUEPRINTS, BlueprintRender, append_routes, call


AUTH_BLUEPRINT = BLUEPRINTS / "auth"
ROUTES_TMPL = "routes.tmpl.py"
APPLICATION_CONTROLLER = "controllers/application.py"

REPLACE_PRE = """

class AppController(Controller"""

WITH_PRE = """
from .concerns import LoadUser, RequireLogin


class AppController(LoadUser, Controller"""

FALLBACK = """from proper import Controller, response

from .concerns import LoadUser, RequireLogin


class AppController(LoadUser, Controller):
"""


def install(app, migration=False):
    """Install user/password authentication support.
    Use `--migration` to generate a migration for creating
    the users table.
    """
    curr_appc = app.root_path / APPLICATION_CONTROLLER
    if not curr_appc.is_file():
        raise ValueError(f"{str(curr_appc)} not found")

    text = curr_appc.read_text()
    if REPLACE_PRE in text:
        if WITH_PRE not in text:
            text = text.replace(REPLACE_PRE, WITH_PRE)
    elif FALLBACK not in text:
        text = f"{FALLBACK}{text}"
    curr_appc.write_text(text)

    bp = BlueprintRender(
        AUTH_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
        },
        ignore=[ROUTES_TMPL],
    )
    bp()

    routes_tmpl = AUTH_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)

    if migration:
        call('proper db revision "Create users table"')
