from proper import Controller, get, status
from proper.helpers import DotDict


class AppController(Controller):
    def render(self):
        return f"{self.response.component} was rendered"

    def index(self):
        pass


class DefaultTemplate(AppController):
    def rendered(self, *kwargs):
        pass


def test_default_component(app, web):
    app.routes = [get("/", to=DefaultTemplate.rendered)]
    resp = web.get("/")

    assert resp.text == "DefaultTemplate.Rendered was rendered"


class CustomTemplate(AppController):
    def set_component(self):
        self.response.component = "FromController"


def test_custom_component(app, web):
    app.routes = [get("/", to=CustomTemplate.set_component)]
    resp = web.get("/")

    assert resp.text == "FromController was rendered"


class ETagged(AppController):
    def index(self):
        self.response.fresh_when(etag=123)
        self.response.component = "index.jinja"


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
    assert resp.headers["Set-Cookie"].startswith("_session")


class DisableCookies(AppController):
    def index(self):
        self.response.set_cookie("foo", "bar")
        self.response.disable_cookies = True
        self.response.set_cookie("lorem", "ipsum")


def test_disable_cookies(app, web):
    app.router.routes = [get("/", to=DisableCookies.index)]
    resp = web.get("/")
    assert "Set-Cookie" not in resp.headers


class Redirect(AppController):
    def show(self, *kwargs):
        pass

    def external(self):
        self.response.redirect_to("http://example.com")

    def local(self):
        self.response.redirect_to("/local/url")

    def verbose(self):
        self.response.redirect_to("Redirect.show", id=1, slug="something")

    def compact(self):
        post = DotDict({"id": 1, "slug": "something"})
        self.response.redirect_to("Redirect.show", post)


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
