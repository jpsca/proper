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


def cb1(_req, resp, _app):
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-cb1-"


def cb2(_req, resp, _app):
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-cb2-"


def cb3(_req, resp, _app):
    print(resp.headers)
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-cb3-"


def cb_stop(_req, resp, _app):
    resp.stop = True


def cb_template(req, resp, _app):
    resp.template = "cb_custom.mako"


class PipelineCalled(AppController):
    _before_action = [ cb1, cb2, cb3 ]
    _after_action = [ cb1, cb2, cb3 ]

    def append(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_cbs_called(app, web):

    app.routes = [scope("/")(get("/", to=PipelineCalled.append))]
    resp = web.get("/")

    expected = "-cb1--cb2--cb3--index--cb1--cb2--cb3-"
    assert resp.headers["X-Test"] == expected


class Stopcb(AppController):
    _before_action = [ cb1, cb_stop, cb3 ]
    _after_action = [ cb1, cb_stop, cb3 ]

    def append(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_stop_in_cbs(app, web):
    app.routes = [scope("/")(get("/", to=Stopcb.append))]
    resp = web.get("/")

    assert resp.headers["X-Test"] == "-cb1-"


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


class CustomTemplateFromcb(AppController):
    _before_action = [ cb_template ]

    def append(self, req, resp):
        resp.body = (resp.body or "") + "-index-"

    def rendered(self, req, resp, *args):
        pass


def test_custom_template_from_cb(app, web):
    app.routes = [scope("/")(get("/", to=CustomTemplateFromcb.append))]

    app.routes = [scope("/")(get("", to=CustomTemplateFromcb.rendered))]
    resp = web.get("/")

    assert resp.text == "<html>cb_custom.mako was rendered</html>"
