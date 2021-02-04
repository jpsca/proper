import re
from pathlib import Path

from proper.helpers import BLUEPRINTS, get_blueprint_render, printf


ROUTES_TMPL = "routes.py.tmpl"
RE_CLOSE_ROUTES = re.compile(r",?[\s\n]*][\s\n]*$")


def _extend_routes(app, pascal_name, actions):
    if not actions:
        return
    render = get_blueprint_render(BLUEPRINTS)
    new_routes = render(ROUTES_TMPL, pascal_name=pascal_name, actions=actions)
    routes_path = app.root_path / "routes.py"
    routes = routes_path.read_text()
    match = RE_CLOSE_ROUTES.search(routes)
    if match:
        routes = routes[:match.start()].rstrip()
    routes_path.write_text(routes + new_routes)
    printf("updated", str(routes_path), color="yellow")
