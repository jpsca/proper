from proper import (
    DotDict,
    View,
    get,
    status,
)
from proper.concerns import Session
from proper.current import response


# -- ETAG --


class ETagged(View):
    def index(self):
        response.fresh_when(etag=123)
        return "Hello world"


def test_if_none_match(app):
    app.routes = [get("/", to=ETagged.index)]

    resp = app.get("/")
    assert resp.status == status.ok
    assert resp.body == "Hello world"

    print(resp.headers)
    resp = app.get("/", headers={"HTTP_IF_NONE_MATCH": resp.headers["etag"]})
    assert resp.status == status.not_modified
    assert resp.body == ""


# -- SESSION --


class Session(View):
    concerns = [Session]

    def update(self):
        response.session["foo"] = "bar"


def test_set_session(app):
    app.router.routes = [get("/session", to=Session.update)]
    resp = app.get("/session")
    print(resp.headers)
    assert "set-cookie" in resp.headers
    assert resp.headers["set-cookie"].startswith("_session")


# -- COOKIE --


class DisableCookies(View):
    def index(self):
        response.set_cookie("foo", "bar")
        response.disable_cookies = True
        response.set_cookie("lorem", "ipsum")


def test_disable_cookies(app):
    app.router.routes = [get("/", to=DisableCookies.index)]
    resp = app.get("/")
    assert "set-cookie" not in resp.headers


# -- REDIRECT --


class Redirect(View):
    def show(self, *kwargs):
        pass

    def external(self):
        response.redirect_to("http://example.com")

    def local(self):
        response.redirect_to("/local/url")

    def verbose(self):
        response.redirect_to("Redirect.show", id=1, slug="something")

    def compact(self):
        post = DotDict({"id": 1, "slug": "something"})
        response.redirect_to("Redirect.show", post)


def test_redirect_to(app):
    app.routes = [
        get("/posts/:id<int>/:slug", to=Redirect.show, name="Redirect.show"),
        get("/external", to=Redirect.external),
        get("/local", to=Redirect.local),
        get("/verbose", to=Redirect.verbose),
        get("/compact", to=Redirect.compact),
    ]

    resp = app.get("/external")
    assert resp.status == status.see_other
    assert resp.headers["location"] == "http://example.com"

    resp = app.get("/local")
    assert resp.headers["location"] == "/local/url"

    resp = app.get("/verbose")
    assert resp.headers["location"] == "/posts/1/something"

    resp = app.get("/compact")
    assert resp.headers["location"] == "/posts/1/something"
