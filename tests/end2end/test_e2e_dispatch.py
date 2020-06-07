from proper import get, BaseController, status


def test_controller_dispatch(app, web):
    app.router.routes = [get("/", to="Pages.index")]
    resp = web.get("/")
    assert resp.status == status.ok


class AppController(BaseController):
    def _render(self, req, resp):
        return f"<html>{resp.template} was rendered</html>"


class CallRender(AppController):
    def rendered(self, req, resp, *args):
        pass


def test_call_render(app, web):
    app.routes = [get("/", to=CallRender.rendered)]
    resp = web.get("/")

    assert resp.text == "<html>call_render/rendered was rendered</html>"


class CustomTemplate(AppController):
    def set_template(self, req, resp):
        resp.template = "from_controller.jinja"


def test_custom_template(app, web):
    app.routes = [get("/", to=CustomTemplate.set_template)]
    resp = web.get("/")

    assert resp.text == "<html>from_controller.jinja was rendered</html>"
