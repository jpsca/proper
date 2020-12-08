from proper import App, BaseController, get


class AppController(BaseController):
    def _render(self, req, resp):
        return resp.template


class Empty(AppController):
    def index(self, req, resp):
        pass


def test_set_session(app, web):
    app.router.routes = [get("/", to=Empty.index)]
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
