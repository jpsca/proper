import json
import logging
from datetime import datetime

import peewee as pw
import pytest

from proper import App, Controller, current, debug_toolbar
from proper.core.response import Response
from proper.debug_toolbar.record import active
from proper.debug_toolbar.toolbar import (
    MAX_REDIRECTS,
    _header_texts,
    _LogHandler,
    _read,
    _texts,
    mask_repr,
)
from proper.models import ProperModel


VIEWS = {
    "layouts/base.jx": """{#def title="" #}
<!DOCTYPE html>
<html>
<head><title>{{ title }}</title></head>
<body>{{ content }}</body>
</html>
""",
    "layouts/auth.jx": """{#import "./base.jx" as Layout #}
{#def title="" #}
<Layout title={{ title }}><main>{{ content }}</main></Layout>
""",
    "form.jx": """{#def action="" #}
<form method="post" action="{{ action }}">{{ content }}</form>
""",
    "session/new.jx": """{#import "layouts/auth.jx" as Layout #}
{#import "form.jx" as Form #}
{#def form #}
<Layout title="Sign in">
  <Form action={{ url_for("Session.create") }}>
    <input name="login" value="{{ form.login }}">
    <input name="password" type="password">
  </Form>
</Layout>
""",
    "fruit/index.jx": """{#import "layouts/base.jx" as Layout #}
{#def fruits #}
<Layout title="Fruits">
  {% for fruit in fruits %}<p>{{ fruit.name }}</p>{% endfor %}
</Layout>
""",
}


class Fruit(ProperModel):
    name = pw.CharField()


class SignInForm:
    def __init__(self, params):
        self.login = params.get("login") or ""
        self.password = params.get("password") or ""

    def __repr__(self):
        return f"SignInForm(login={self.login!r}, password={self.password!r})"


# The folder of the views of a controller is the name of its module
class PublicController(Controller):
    __module__ = "fruits.controllers.public_controller"

    def health(self):
        return "<!DOCTYPE html>\n<html><body>OK</body></html>\n"


class SessionController(Controller):
    __module__ = "fruits.controllers.session_controller"

    def new(self):
        self.form = SignInForm(self.params)

    def create(self):
        self.form = SignInForm(self.params)
        return self.redo()


class FruitController(Controller):
    __module__ = "fruits.controllers.fruit_controller"

    def index(self):
        self.fruits = list(Fruit.select())


class AccountController(Controller):
    __module__ = "fruits.controllers.account_controller"

    def show(self):
        # Nobody is signed in
        self.response.redirect_to("Session.new")


@pytest.fixture()
def app(tmp_path):
    """An app with a few pages: one without a view, one with a form, one
    that runs a query and one that redirects."""
    for name, source in VIEWS.items():
        path = tmp_path / "views" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)

    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": False})
    current.app = app
    app.catalog.add_folder(tmp_path / "views")

    router = app.router
    router.get("up")(PublicController.health)
    router.get("sign-in")(SessionController.new)
    router.post("sign-in")(SessionController.create)
    router.get("fruits")(FruitController.index)
    router.get("account")(AccountController.show)

    db = app.db["main"]
    db.bind([Fruit])
    db.connect(reuse_if_open=True)
    db.create_tables([Fruit])
    Fruit.create(name="lime")
    yield app
    db.close()


@pytest.fixture()
def toolbar(app):
    """The toolbar of the app of the test."""
    return app.install_debug_toolbar()


def test_bar_is_added_to_html_pages(client, toolbar):
    app = client.app
    response = client.get(app.url_for("Public.health"))

    assert response.status == 200
    record = toolbar.store.latest()[0]
    assert f'data-request-id="{record.id}"' in response.body
    assert f'href="/__debug__/{record.id}"' in response.body
    # Before the end of the body, and the page is still whole
    assert response.body.rstrip().endswith("</html>")
    assert response.body.index("proper-debug-toolbar") < response.body.rindex("</body>")
    assert response.headers["x-request-id"] == record.id


def test_record_has_the_route_and_the_time(client, toolbar):
    app = client.app
    client.get(app.url_for("Public.health"))

    record = toolbar.store.latest()[0]
    assert record.method == "GET"
    assert record.path == "/up"
    assert record.status == 200
    assert record.controller == "PublicController"
    assert record.action == "health"
    assert record.target == "PublicController.health"
    assert record.ms > 0
    assert [name for name, _ms in record.steps][-2:] == [
        "dispatch",
        "update_session_cookie",
    ]
    assert sum(ms for _name, ms in record.steps) <= record.ms


def test_queries_are_recorded(client, toolbar):
    response = client.get("/fruits")

    assert response.status == 200
    assert "lime" in response.body

    record = toolbar.store.latest()[0]
    assert record.queries
    query = record.queries[0]
    assert query.db == "main"
    assert query.sql.upper().startswith("SELECT")
    assert query.ms >= 0
    # The line of the app that ran it, not one of peewee or of the toolbar
    assert query.origin.startswith("tests/test_debug_toolbar.py:")
    assert query.origin.endswith(" in index")
    assert record.sql_ms == sum(q.ms for q in record.app_queries)


def test_repeated_queries_are_counted():
    record = debug_toolbar.Record(id="x", started_at=datetime.now())
    record.queries = [
        debug_toolbar.Query(db="main", sql="SELECT 1", params="", ms=1),
        debug_toolbar.Query(db="main", sql="SELECT 1", params="", ms=1),
        debug_toolbar.Query(db="main", sql="SELECT 2", params="", ms=1),
    ]

    record.count_repeated()

    assert [query.repeated for query in record.queries] == [2, 2, 1]
    assert record.repeated_count == 2


def test_cache_queries_are_counted_apart():
    # The cache reads one key per query: the same SQL, many times
    record = debug_toolbar.Record(id="x", started_at=datetime.now())
    record.queries = [
        debug_toolbar.Query(db="proper_cache", sql="SELECT k", params="", ms=1, cache=True),
        debug_toolbar.Query(db="proper_cache", sql="SELECT k", params="", ms=1, cache=True),
        debug_toolbar.Query(db="main", sql="SELECT 1", params="", ms=2),
    ]

    record.count_repeated()

    assert record.repeated_count == 0
    assert [query.db for query in record.app_queries] == ["main"]
    assert record.sql_ms == 2
    assert record.cache_ms == 2


def test_queries_outside_a_request_are_ignored(toolbar):
    Fruit.select().count()

    assert len(toolbar.store) == 0


def test_secrets_are_redacted(client, toolbar):
    app = client.app
    client.post(
        app.url_for("Session.create"),
        body={"login": "someone", "password": "a-long-secret"},
    )

    record = toolbar.store.latest()[0]
    form = dict(record.request_data)["Form"]
    assert form["login"] == "someone"
    assert "a-long-secret" not in form["password"]

    page = client.get(f"/__debug__/{record.id}")
    assert "a-long-secret" not in page.body


def test_redirects_are_recorded_without_a_bar(client, toolbar):
    # Not signed in: the page of the account redirects to the sign-in
    response = client.get("/account")

    assert response.status in (302, 303)
    record = toolbar.store.latest()[0]
    assert record.status == response.status
    assert "proper-debug-toolbar" not in response.body


def test_only_whole_html_pages_get_a_bar(app, toolbar):
    record = debug_toolbar.Record(id="x", started_at=datetime.now())

    json = Response(app)
    json.mimetype = "application/json"
    json.body = '{"html": "<body></body>"}'
    toolbar.inject(record, json)
    assert "proper-debug-toolbar" not in json.body

    # A Turbo Frame, or any other fragment
    fragment = Response(app)
    fragment.body = "<turbo-frame id='a'>Hello</turbo-frame>"
    toolbar.inject(record, fragment)
    assert "proper-debug-toolbar" not in fragment.body

    page = Response(app)
    page.body = "<html><body>Hello</body></html>"
    toolbar.inject(record, page)
    assert page.body.endswith("</div></body></html>")


def test_request_page(client, toolbar):
    app = client.app
    client.get(app.url_for("Public.health") + "?q=limes")
    record = toolbar.store.latest()[0]

    page = client.get(f"/__debug__/{record.id}")

    assert page.status == 200
    assert "PublicController" in page.body
    assert "limes" in page.body
    assert "dispatch" in page.body
    # The pages of the toolbar have no bar, and are not recorded
    assert "proper-debug-toolbar" not in page.body
    assert len(toolbar.store) == 1


def test_request_page_of_an_unknown_request(client, toolbar):
    page = client.get("/__debug__/nope")

    assert page.status == 404
    assert "Request not found" in page.body


def test_requests_page(client, toolbar):
    app = client.app
    client.get(app.url_for("Public.health"))
    client.get("/account")

    page = client.get("/__debug__")

    assert page.status == 200
    newest, oldest = toolbar.store.latest()
    assert page.body.index(newest.id) < page.body.index(oldest.id)


def test_assets_are_not_recorded(client, toolbar):
    client.get("/assets/css/base.css")

    assert len(toolbar.store) == 0


def test_store_keeps_the_last_ones():
    store = debug_toolbar.Store(size=2)
    for name in "abc":
        store.add(debug_toolbar.Record(id=name, started_at=datetime.now()))

    assert [record.id for record in store.latest()] == ["c", "b"]
    assert store.get("a") is None


def test_disabled_toolbar(client, toolbar):
    app = client.app
    toolbar.enabled = False

    response = client.get(app.url_for("Public.health"))

    assert "proper-debug-toolbar" not in response.body
    assert len(toolbar.store) == 0
    assert client.get("/__debug__").status == 404


@pytest.fixture()
def record(toolbar):
    """A record that is the one of the request being answered."""
    record = debug_toolbar.Record(id="x", started_at=datetime.now())
    token = active.set(record)
    yield record
    active.reset(token)


def test_rendered_views_are_recorded(client, toolbar):
    app = client.app
    client.get(app.url_for("Session.new"))

    record = toolbar.store.latest()[0]
    assert [render.view for render in record.renders] == ["session/new.jx"]
    render = record.renders[0]
    assert 0 < render.ms <= record.ms
    assert "form" in render.variables
    assert "request" not in render.variables
    # `self.params` keeps its value in `_params`
    assert "_params" not in render.variables
    assert record.render_ms == render.ms


def test_secrets_in_the_repr_of_a_view_variable_are_masked():
    text = mask_repr("SignInForm(login='someone', password='a-long-secret')")
    assert text == "SignInForm(login='someone', password='▒▒▒▒')"

    text = mask_repr("""{'api_token': "it's long", 'name': 'ok'}""")
    assert text == "{'api_token': '▒▒▒▒', 'name': 'ok'}"


def test_cache_calls_are_recorded(app, record):
    app.cache.set("fruit", "lime")
    app.cache.get("fruit")
    app.cache.read_multi("fruit", "tree")
    app.cache.get_or_set("tree", "lemon")

    calls = [(call.op, call.key) for call in record.cache_calls]
    assert calls == [
        ("set", "fruit"),
        ("get", "fruit"),
        # One call, not one per key
        ("read_multi", "fruit, tree"),
        # `get_or_set` is a `get` and, after a miss, a `set`
        ("get", "tree"),
        ("set", "tree"),
    ]
    assert record.cache_calls[0].hit is None
    # The tests run without a cache store (`NoCache`): every read is a miss
    assert record.cache_hits == 0
    assert record.cache_misses == 3


def test_cache_calls_outside_a_request_are_ignored(app, toolbar):
    app.cache.get("fruit")

    assert len(toolbar.store) == 0


def test_log_lines_are_recorded(record):
    log = logging.getLogger("fruits.tests")
    log.warning("%s limes left", 2)
    log.error("postgres://user:hunter2@host/db is down")
    try:
        raise ValueError("sour")
    except ValueError:
        log.exception("Squeezing failed")

    lines = [(line.level, line.logger, line.message) for line in record.logs]
    assert lines == [
        ("WARNING", "fruits.tests", "2 limes left"),
        ("ERROR", "fruits.tests", "postgres://user:▒▒▒▒@host/db is down"),
        ("ERROR", "fruits.tests", "Squeezing failed\nValueError: sour"),
    ]
    assert record.problems == 3
    assert all(line.at >= 0 for line in record.logs)


def test_log_lines_of_a_request(client, toolbar):
    client.get("/nothing-here")

    record = toolbar.store.latest()[0]
    assert any("MatchNotFound" in line.message for line in record.logs)


def test_a_redirect_is_linked_to_the_request_that_follows(client, toolbar):
    redirect = client.get("/account")
    location = redirect.headers["location"]

    page = client.get(location)

    newest, oldest = toolbar.store.latest()
    assert oldest.redirect_to == location
    assert newest.redirected_from == oldest.id
    assert f'href="/__debug__/{oldest.id}"' in page.body
    assert "GET /account" in page.body

    # Only the request right after the redirect
    client.get(location)
    assert toolbar.store.latest()[0].redirected_from == ""

    details = client.get(f"/__debug__/{newest.id}")
    assert "Redirected from" in details.body


def test_summary_of_a_request(client, toolbar):
    app = client.app
    client.get(app.url_for("Public.health"), headers={"x-sec-purpose": "prefetch"})
    record = toolbar.store.latest()[0]

    response = client.get(f"/__debug__/{record.id}/summary")

    assert response.status == 200
    assert response.mimetype == "application/json"
    assert json.loads(response.body) == {
        "id": record.id,
        "status": 200,
        "kind": "ok",
        "method": "GET",
        "path": "/up",
        "ms": round(record.ms, 1),
        "sql": 0,
        "prefetch": True,
    }
    assert client.get("/__debug__/nope/summary").status == 404


def test_request_page_has_every_panel(client, toolbar):
    app = client.app
    client.post(
        app.url_for("Session.create"),
        body={"login": "someone", "password": "a-long-secret"},
    )
    record = toolbar.store.latest()[0]

    page = client.get(f"/__debug__/{record.id}")

    assert page.status == 200
    for panel in ("time", "sql", "views", "cache", "logs", "request", "response"):
        assert f'<h2 id="{panel}"' in page.body
    assert "session/new.jx" in page.body
    assert "a-long-secret" not in page.body


def test_components_of_a_view_are_recorded(client, toolbar):
    app = client.app
    client.get(app.url_for("Session.new"))

    render = toolbar.store.latest()[0].renders[0]
    rows = [(depth, call.view) for depth, call in render.rows]
    assert rows[0] == (0, "session/new.jx")
    assert (1, "layouts/auth.jx") in rows
    assert (2, "layouts/base.jx") in rows
    assert (1, "form.jx") in rows
    assert render.component_count == len(rows)

    tree = render.tree
    assert tree.ms == render.ms
    assert all(child.ms <= tree.ms for child in tree.children)
    assert 0 <= tree.self_ms <= tree.ms


def test_components_rendered_in_a_row_are_one_line():
    parent = debug_toolbar.ComponentCall(view="list.jx")
    for _ in range(3):
        parent.add(debug_toolbar.ComponentCall(view="row.jx", ms=2, queries=1))
    parent.add(debug_toolbar.ComponentCall(view="footer.jx", ms=1))
    parent.add(debug_toolbar.ComponentCall(view="row.jx", ms=2))

    assert [(c.view, c.count, c.ms, c.queries) for c in parent.children] == [
        ("row.jx", 3, 6, 3),
        ("footer.jx", 1, 1, 0),
        ("row.jx", 1, 2, 0),
    ]

    # One with components inside is kept apart
    card = debug_toolbar.ComponentCall(view="row.jx", ms=2)
    card.add(debug_toolbar.ComponentCall(view="badge.jx", ms=1))
    parent.add(card)
    assert len(parent.children) == 4
    assert [depth for depth, _call in parent.rows()] == [0, 1, 1, 1, 1, 2]
    assert card.self_ms == 1


def test_queries_know_the_component_that_ran_them(app, record):
    source = "{#def fruits #}{% for fruit in fruits %}{{ fruit.name }}{% endfor %}"

    app.catalog.render_string(source, fruits=Fruit.select())

    render = record.renders[0]
    assert render.tree.queries == 1
    assert render.variables.keys() == {"fruits"}
    query = record.queries[0]
    assert query.component == render.view
    assert not record.rendering


def test_request_page_has_the_components(client, toolbar):
    app = client.app
    client.get(app.url_for("Session.new"))
    record = toolbar.store.latest()[0]

    page = client.get(f"/__debug__/{record.id}")

    assert "layouts/base.jx" in page.body
    assert "Own time" in page.body


def test_install_again_returns_the_same_toolbar(app, toolbar):
    routes = len(app.routes)

    assert app.install_debug_toolbar() is toolbar
    assert app.debug_toolbar is toolbar
    assert len(app.routes) == routes
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, _LogHandler)]
    assert len(handlers) == 1


def test_each_app_has_its_own_toolbar(app, toolbar):
    other = App(__name__, {"SECRET_KEYS": ["*" * 50]})
    assert other.debug_toolbar is None

    other_toolbar = other.install_debug_toolbar()

    assert other_toolbar is not toolbar
    assert other_toolbar.app is other
    assert app.debug_toolbar is toolbar
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, _LogHandler)]
    assert len(handlers) == 1


def test_pages_of_an_app_without_a_toolbar(client):
    debug_toolbar.DebugToolbarController.connect(client.app.router)

    assert client.get("/__debug__").status == 404


def test_app_without_assets_and_with_a_database_turned_off(app, request):
    app.config.ASSETS_URL = ""
    app.db["archive"] = None

    toolbar = request.getfixturevalue("toolbar")

    assert toolbar._ignored_paths == ("/__debug__",)
    assert len(app.db["main"].query_hooks) == 1


def test_a_bug_of_the_toolbar_does_not_break_the_page(client, toolbar):
    def inject(record, response):
        raise RuntimeError("a bug")

    toolbar.inject = inject

    response = client.get("/up")

    assert response.status == 200
    assert response.body.rstrip().endswith("</html>")
    assert "proper-debug-toolbar" not in response.body


def test_views_rendered_outside_a_request_are_ignored(app, toolbar):
    html = app.catalog.render_string("{#def name #}Hello {{ name }}", name="lime")

    assert html == "Hello lime"
    assert len(toolbar.store) == 0


def test_only_the_last_redirects_are_remembered(toolbar):
    for number in range(MAX_REDIRECTS + 1):
        record = debug_toolbar.Record(id=str(number), started_at=datetime.now())
        record.redirect_to = f"/page/{number}"
        toolbar._remember_redirect(record)

    assert toolbar._followed_redirect("/page/0") == ""
    assert toolbar._followed_redirect("/page/1") == "1"
    assert toolbar._followed_redirect(f"/page/{MAX_REDIRECTS}") == str(MAX_REDIRECTS)


def test_query_without_a_line_of_the_project(toolbar, record):
    toolbar._project = "/not/this/project/"

    Fruit.select().count()

    assert record.queries[0].origin == ""


def test_route_without_an_action(client, toolbar):
    client.app.router.get("old-up", redirect="/up")

    response = client.get("/old-up")

    record = toolbar.store.latest()[0]
    assert record.status == response.status
    assert record.kind == "redirect"
    assert record.redirect_to == "/up"
    assert record.route_path == "/old-up"
    assert record.controller == ""
    assert record.action == ""
    assert record.target == record.route_name


def test_kind_of_a_server_error():
    record = debug_toolbar.Record(id="x", started_at=datetime.now())
    record.status = 500

    assert record.kind == "error"


def test_log_line_with_its_error_in_the_message(record):
    log = logging.getLogger("fruits.tests")
    try:
        raise ValueError("sour")
    except ValueError as error:
        log.exception("ValueError: %s", error)

    assert [line.message for line in record.logs] == ["ValueError: sour"]


def test_log_line_that_cannot_be_formatted(record, capsys):
    # Not through a logger: the handler of pytest raises for such a line
    line = logging.LogRecord(
        "fruits.tests", logging.WARNING, __file__, 1, "%d limes left", ("two",), None
    )
    _LogHandler().handle(line)

    assert record.logs == []
    # `logging` reports it, as it does for any other handler
    assert "TypeError" in capsys.readouterr().err


def test_cache_calls_without_a_key_or_with_many(app, record):
    app.cache.write_multi({"fruit": "lime", "tree": "lemon"})
    app.cache.clear()

    calls = [(call.op, call.key, call.hit) for call in record.cache_calls]
    assert calls == [
        ("write_multi", "fruit, tree", None),
        ("clear", "", None),
    ]


def test_store_can_be_cleared_and_iterated():
    store = debug_toolbar.Store()
    for name in "ab":
        store.add(debug_toolbar.Record(id=name, started_at=datetime.now()))

    assert [record.id for record in store] == ["b", "a"]

    store.clear()
    assert len(store) == 0


def test_data_that_cannot_be_read_is_shown_empty():
    assert _read(lambda: 1 / 0) is None
    assert _texts(_read(lambda: 1 / 0)) == {}
    # Not a mapping
    assert _texts(3) == {}


def test_response_headers_are_redacted_and_joined():
    texts = _header_texts([
        ("x-api-token", "a-long-secret"),
        ("x-empty-token", ""),
        ("set-cookie", "a=1"),
        ("set-cookie", "b=2"),
    ])

    assert texts == {
        "x-api-token": "a-lo▒▒▒▒▒▒▒▒▒",
        "x-empty-token": "",
        "set-cookie": "a=1\nb=2",
    }
