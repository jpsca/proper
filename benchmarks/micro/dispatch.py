"""One request through a controller shaped like a real one: four `before`
callbacks (origin, CSRF, locale, load the record), one `after`, and a view
inferred from the action, with a browser's `Accept` header.

Measures what `proper.compile.dispatch` decides once per (controller,
action) instead of once per request. Runs in process, on one thread,
through the WSGI entry, without a server.

    uv run python benchmarks/micro/dispatch.py
"""
import sys
import types
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from _common import best_of

from proper import App, Controller, Route
from proper.test_client import make_test_request


ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


class ItemsController(Controller):
    # A route resolves its controller by module and name; the module is
    # registered below so the view prefix is `items/`, as in an app.
    __module__ = "bench.controllers.items_controller"

    before = [
        {"do": "check_request_origin"},
        {"do": "check_csrf_token"},
        {"do": "set_locale"},
        {"do": "set_item", "exclude": ["index", "new", "create"]},
        {"do": "validate_form", "only": ["create", "update"]},
    ]
    after = {"do": "set_vary", "only": "show"}

    def check_request_origin(self):
        pass

    def check_csrf_token(self):
        pass

    def set_locale(self):
        pass

    def set_item(self):
        self.item = "Item " + self.params["id"]

    def validate_form(self):
        pass

    def set_vary(self):
        self.response.headers["vary"] = "Accept"

    def show(self):
        pass


def make_app(views: Path) -> App:
    module = types.ModuleType(ItemsController.__module__)
    module.__dict__["ItemsController"] = ItemsController
    sys.modules[module.__name__] = module

    (views / "items").mkdir(parents=True)
    (views / "items" / "show.jx").write_text("{#def item #}<p>{{ item }}</p>")

    app = App(__name__, {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        # compiled next to the views, in the temporary folder
        "COMPILED_PATH": str(views.parent / "_compiled"),
    })
    app.catalog.auto_reload = False
    app.catalog.add_folder(views)
    app.router.add_route(Route("GET", "items/:id", to=ItemsController.show))
    app.lower()
    return app


def main() -> None:
    with TemporaryDirectory() as tmp:
        app = make_app(Path(tmp) / "views")
        headers = {"host": "127.0.0.1", "accept": ACCEPT}

        def request() -> None:
            req = make_test_request("/items/7", headers=headers, app=app)
            response = app._respond_sync(req, BytesIO(b"").read)
            assert response.status == 200, (response.status, response.body)

        print(f"GET /items/7, 4 before + 1 after, inferred view: {best_of(request):.1f} us/request")


if __name__ == "__main__":
    main()
