"""`proper routes`: the TO column names the class the request runs on."""

from proper import App, Controller
from proper.cli.app_cli import get_routes_cmd


class ApplicationController(Controller):
    def index(self): ...

    def show(self): ...


class ArticleController(ApplicationController):
    def edit(self): ...


def run_routes(app, capsys) -> dict[str, str]:
    get_routes_cmd(app)(None)
    out = capsys.readouterr().out
    rows = {}
    for line in out.splitlines():
        words = line.split()
        if len(words) == 5 and words[0] in ("GET", "POST"):
            rows[words[3]] = words[2]
    return rows


def test_inherited_action_of_a_resource_shows_the_routed_class(capsys):
    app = App(__name__, {"SECRET_KEYS": ["*" * 50]})
    app.router.resource("articles")(ArticleController)
    # A route from a method object belongs to the class that defines it.
    app.router.get("feed")(ArticleController.index)
    rows = run_routes(app, capsys)
    assert rows["Article.index"] == "ArticleController.index"
    assert rows["Article.show"] == "ArticleController.show"
    assert rows["Article.edit"] == "ArticleController.edit"
    assert rows["Application.index"] == "ApplicationController.index"
    assert ApplicationController.index is ArticleController.index
