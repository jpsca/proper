from proper import get, BaseController, status
from proper.helpers import Dot


class AppController(BaseController):
    def _render(self, req, resp):
        return f"{resp.template} was rendered"

    def index(self, req, resp):
        pass


class DefaultTemplate(AppController):
    def rendered(self, req, resp, *args):
        pass


def test_default_template(app, web):
    app.routes = [get("/", to=DefaultTemplate.rendered)]
    resp = web.get("/")

    assert resp.text == "default_template/rendered was rendered"


class CustomTemplate(AppController):
    def set_template(self, req, resp):
        resp.template = "from_controller.jinja"


def test_custom_template(app, web):
    app.routes = [get("/", to=CustomTemplate.set_template)]
    resp = web.get("/")

    assert resp.text == "from_controller.jinja was rendered"


class ETagged(AppController):
    def index(self, req, resp):
        resp.fresh_when(etag=123)
        resp.template = "index.jinja"


def test_if_none_match(app, web):
    app.routes = [get("/", to=ETagged.index)]
    resp = web.get("/")
    resp = web.get("/", extra_environ={"HTTP_IF_NONE_MATCH": resp.headers["Etag"]})
    assert resp.status == status.not_modified
    assert resp.text == ""


def test_set_session(app, web):
    app.router.routes = [get("/", to=AppController.index)]
    resp = web.get("/")
    assert "Set-Cookie" in resp.headers
    assert resp.headers["Set-Cookie"].startswith("_proper_session")


class DisableCookies(AppController):
    def index(self, req, resp):
        resp.set_cookie("foo", "bar")
        resp.disable_cookies = True
        resp.set_cookie("lorem", "ipsum")


def test_disable_cookies(app, web):
    app.router.routes = [get("/", to=DisableCookies.index)]
    resp = web.get("/")
    assert "Set-Cookie" not in resp.headers


class Redirect(AppController):
    def show(self, req, resp, *kwargs):
        pass

    def external(self, req, resp):
        resp.redirect_to("http://example.com")

    def local(self, req, resp):
        resp.redirect_to("/local/url")

    def verbose(self, req, resp):
        resp.redirect_to("Redirect.show", id=1, slug="something")

    def compact(self, req, resp):
        post = Dot({"id": 1, "slug": "something"})
        resp.redirect_to("Redirect.show", post)



def test_redirect_to(app, web):
    app.routes = [
        get("/posts/:id<int>/:slug", to=Redirect.show, name="Redirect.show"),
        get("/external", to=Redirect.external),
        get("/local", to=Redirect.local),
        get("/verbose", to=Redirect.verbose),
        get("/compact", to=Redirect.compact),
    ]

    resp = web.get("/external")
    assert resp.status == status.see_other
    assert resp.headers["Location"] == "http://example.com"

    resp = web.get("/local")
    assert resp.headers["Location"] == "/local/url"

    resp = web.get("/verbose")
    assert resp.headers["Location"] == "/posts/1/something"

    resp = web.get("/compact")
    assert resp.headers["Location"] == "/posts/1/something"
