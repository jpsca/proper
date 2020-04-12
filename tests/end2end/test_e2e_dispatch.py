from proper import get, scope, BaseController, status


def test_controller_dispatch(app, web):
    app.router.routes = [
        get("/", to="Pages.index"),
    ]

    resp = web.get("/")
    assert resp.status == status.ok


class AppController(BaseController):
    def _render(self, req, resp):
        return f"<html>{resp.template} was rendered</html>"


def plug1(_req, resp, _app):
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-plug1-"


def plug2(_req, resp, _app):
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-plug2-"


def plug3(_req, resp, _app):
    print(resp.headers)
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-plug3-"


def plug_stop(_req, resp, _app):
    resp.stop = True


def plug_template(req, resp, _app):
    resp.template = "plug_custom.mako"


class PipelineCalled(AppController):
    _plugs = [
        plug1,
        plug2,
        plug3,
    ]

    def append(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_plugs_called(app, web):

    app.routes = [scope("/")(get("/", to=PipelineCalled.append))]
    resp = web.get("/")

    expected = "-plug1--plug2--plug3--index--plug1--plug2--plug3-"
    assert resp.headers["X-Test"] == expected


class StopPlug(AppController):
    _plugs = [
        plug1,
        plug_stop,
        plug3,
    ]

    def append(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_stop_in_plugs(app, web):
    app.routes = [scope("/")(get("/", to=StopPlug.append))]
    resp = web.get("/")

    assert resp.headers["X-Test"] == "-plug1-"


class CallRender(AppController):
    def rendered(self, req, resp, *args):
        pass


def test_call_render(app, web):
    app.routes = [scope("/")(get("/", to=CallRender.rendered))]
    resp = web.get("/")

    assert resp.text == "<html>call_render/rendered was rendered</html>"


class CustomTemplate(AppController):
    def set_template(self, req, resp):
        resp.template = "from_controller.jinja"


def test_custom_temnplate(app, web):
    app.routes = [scope("/")(get("/", to=CustomTemplate.set_template))]
    resp = web.get("/")

    assert resp.text == "<html>from_controller.jinja was rendered</html>"


class CustomTemplateFromPlug(AppController):
    _plugs = [
        plug_template,
    ]

    def append(self, req, resp):
        resp.body = (resp.body or "") + "-index-"

    def rendered(self, req, resp, *args):
        pass


def test_custom_template_from_plug(app, web):
    app.routes = [scope("/")(get("/", to=CustomTemplateFromPlug.append))]

    app.routes = [scope("/")(get("", to=CustomTemplateFromPlug.rendered))]
    resp = web.get("/")

    assert resp.text == "<html>plug_custom.mako was rendered</html>"
