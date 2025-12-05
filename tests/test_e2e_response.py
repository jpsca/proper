import pytest

from proper import Controller, DotDict, status


# -- ETAG --


class ETaggedController(Controller):
    def index(self):
        self.response.fresh_when(etag=123)
        return "Hello world"


def test_if_none_match(app):
    app.router.get("/")(ETaggedController.index)

    resp = app.get("/")
    assert resp.status == status.ok
    assert resp.body == "Hello world"

    print(resp.headers)
    resp = app.get("/", headers={"HTTP_IF_NONE_MATCH": resp.headers.get("ETag")})
    assert resp.status == status.not_modified
    assert resp.body == ""


# -- SESSION --


class SessionController(Controller):
    def update(self):
        self.response.session["foo"] = "bar"


@pytest.mark.skip(reason="Needs investigation")
def test_set_session(app):
    app.router.get("/session")(SessionController.update)
    resp = app.get("/session")
    print(resp.headers)
    assert "Set-Cookie" in resp.headers
    assert resp.headers.get("Set-Cookie").startswith("_session")


# -- COOKIE --


class DisableCookiesController(Controller):
    def index(self):
        self.response.set_cookie("foo", "bar")
        self.response.disable_cookies = True
        self.response.set_cookie("lorem", "ipsum")


def test_disable_cookies(app):
    app.router.get("/")(DisableCookiesController.index)
    resp = app.get("/")
    assert "Set-Cookie" not in resp.headers


# -- REDIRECT --


class RedirectController(Controller):
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


def test_redirect_to(app):
    app.router.get("/posts/:id<int>/:slug")(RedirectController.show)
    app.router.get("/external")(RedirectController.external)
    app.router.get("/local")(RedirectController.local)
    app.router.get("/verbose")(RedirectController.verbose)
    app.router.get("/compact")(RedirectController.compact)

    resp = app.get("/external")
    assert resp.status == status.see_other
    assert resp.headers.get("Location") == "http://example.com"

    resp = app.get("/local")
    assert resp.headers.get("Location") == "/local/url"

    resp = app.get("/verbose")
    assert resp.headers.get("Location") == "/posts/1/something"

    resp = app.get("/compact")
    assert resp.headers.get("Location") == "/posts/1/something"
