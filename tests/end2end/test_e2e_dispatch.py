from proper import get
from proper import scope


def plug1(_req, resp, _app):
    resp.body = (resp.body or "") + "-plug1-"


def plug2(_req, resp, _app):
    resp.body = (resp.body or "") + "-plug2-"


def plug3(_req, resp, _app):
    resp.body = (resp.body or "") + "-plug3-"


def plug_stop(_req, resp, _app):
    resp.stop = True


def plug_template(req, resp, _app):
    resp.template = "plug_custom.mako"


def test_pipeline_called(app, web):
    app.routes = [
        scope("/", pipeline=[plug1, plug2, plug3])(get("/", to="Pages.append"))
    ]
    resp = web.get("/")

    assert resp.text == "-plug1--plug2--plug3--index--plug1--plug2--plug3-"


def test_stop_in_pipeline(app, web):
    app.routes = [
        scope("/", pipeline=[plug1, plug_stop, plug3])(get("/", to="Pages.append"))
    ]
    resp = web.get("/")

    assert resp.text == "-plug1-"


def test_call_render(app, web):
    app.routes = [scope("/")(get("/", to="Pages.rendered"))]
    resp = web.get("/")

    assert resp.text == "<html>pages/rendered was rendered</html>"


def test_custom_temnplate(app, web):
    app.routes = [scope("/")(get("/", to="Pages.set_template"))]
    resp = web.get("/")

    assert resp.text == "<html>from_controller.jinja was rendered</html>"


def test_custom_temnplate_from_plug(app, web):
    app.routes = [
        scope("/", pipeline=[plug_template])(get("", to="Pages.rendered"))
    ]
    resp = web.get("/")

    assert resp.text == "<html>plug_custom.mako was rendered</html>"
