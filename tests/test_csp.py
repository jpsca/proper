"""The helpers for a `Content-Security-Policy`: the hash of the import map
and the nonce of each visitor."""
import base64
import hashlib

import pytest

from proper import App, TestClient, current
from proper.constants import CSP_NONCE_SESSION_KEY, SESSION_COOKIE_NAME
from proper.controller import Controller
from proper.core.response import Response
from proper.helpers import csp_hash, csp_meta_tag, csp_nonce, importmap_json
from proper.router import Route


SEEN = {}


class Page(Controller):
    def index(self):
        SEEN["nonce"] = nonce = self.response.csp_nonce
        self.response.headers["Content-Security-Policy"] = f"script-src 'nonce-{nonce}'"
        return f'<script nonce="{csp_nonce()}">1</script>'

    def plain(self):
        return "no nonce here"

    def no_cookies(self):
        self.response.disable_cookies = True
        return self.response.csp_nonce


@pytest.fixture()
def csp_app(app):
    app.router.add_route(Route(method="GET", path="/", to=Page.index))
    app.router.add_route(Route(method="GET", path="/plain", to=Page.plain))
    app.router.add_route(Route(method="GET", path="/no-cookies", to=Page.no_cookies))
    app.router.static("/assets", root="/tmp/assets", name="assets")
    return app


def _session_cookie(resp):
    """The session cookie the response set, as the next request sends it."""
    for value in resp.headers.getall("set-cookie"):
        if value.startswith(f"{SESSION_COOKIE_NAME}="):
            return value.split(";")[0]
    return None


class TestCspHash:
    def test_it_is_the_sha256_of_the_text_in_base64_with_quotes(self):
        # The example of the CSP specification
        assert csp_hash("alert('Hello, world.');") == (
            "'sha256-qznLcsROx4GACP2dm0UCKCzCG+HiZ1guq6ZZDob/Tng='"
        )

    def test_the_text_is_hashed_as_utf8(self):
        digest = hashlib.sha256("ñ".encode()).digest()
        assert csp_hash("ñ") == f"'sha256-{base64.b64encode(digest).decode()}'"


class TestImportmapHash:
    def test_it_is_the_hash_of_the_script_render_importmap_writes(self, csp_app):
        html = str(csp_app.catalog.globals["render_importmap"]())
        text = html[html.index(">") + 1:html.index("</script>")]
        assert text == importmap_json(csp_app)
        assert csp_app.importmap_csp_hash == csp_hash(text)

    def test_it_changes_with_the_import_map(self, csp_app):
        before = csp_app.importmap_csp_hash
        assert csp_app.importmap_csp_hash == before
        csp_app.config.IMPORT_MAP = {**csp_app.config.IMPORT_MAP, "mylib": "/static/mylib.js"}
        after = csp_app.importmap_csp_hash
        assert after != before
        assert after == csp_hash(importmap_json(csp_app))

    def test_each_app_has_its_own(self, csp_app):
        other = App(__name__, {"SECRET_KEYS": ["*" * 50], "IMPORT_MAP": {"x": "/x.js"}})
        other.router.static("/assets", root="/tmp/assets", name="assets")
        assert other.importmap_csp_hash != csp_app.importmap_csp_hash
        assert csp_app.importmap_csp_hash == csp_hash(importmap_json(csp_app))


class TestNonce:
    def test_it_is_made_once_and_kept_in_the_session(self, app):
        response = Response(app)
        nonce = response.csp_nonce
        assert len(nonce) >= 16
        assert response.csp_nonce == nonce
        assert response.session == {CSP_NONCE_SESSION_KEY: nonce}

    def test_each_visitor_has_its_own(self, app):
        assert Response(app).csp_nonce != Response(app).csp_nonce

    def test_the_one_in_the_session_is_used(self, app):
        response = Response(app)
        response.session = {CSP_NONCE_SESSION_KEY: "abcdefghijklmnop", "cart": [1]}
        assert response.csp_nonce == "abcdefghijklmnop"
        assert response.session["cart"] == [1]

    @pytest.mark.parametrize(
        "value", ["", "short", "has spaces in the value", "quote'in-the-nonce-value", 42, None, ["x"]]
    )
    def test_a_value_that_is_not_a_nonce_is_replaced(self, app, value):
        response = Response(app)
        response.session = {CSP_NONCE_SESSION_KEY: value}
        nonce = response.csp_nonce
        assert nonce != value
        assert response.session[CSP_NONCE_SESSION_KEY] == nonce

    def test_the_helpers_of_the_views_give_the_one_of_the_response(self, app):
        current.response = response = Response(app)
        assert app.catalog.globals["csp_nonce"] is csp_nonce
        assert app.catalog.globals["csp_meta_tag"] is csp_meta_tag
        assert csp_nonce() == response.csp_nonce
        tag = csp_meta_tag()
        assert tag == f'<meta name="csp-nonce" nonce="{response.csp_nonce}">'
        assert tag.__html__() == tag  # not escaped again in a view

    def test_a_visitor_keeps_its_nonce(self, csp_app):
        client = TestClient(csp_app)
        first = client.get("/")
        nonce = SEEN["nonce"]
        assert first.headers["content-security-policy"] == f"script-src 'nonce-{nonce}'"
        assert first.body == f'<script nonce="{nonce}">1</script>'
        cookie = _session_cookie(first)
        assert cookie

        second = client.get("/", headers={"cookie": cookie})
        assert SEEN["nonce"] == nonce
        assert second.body == first.body
        assert _session_cookie(second) is None  # the session did not change

    def test_another_visitor_gets_another(self, csp_app):
        client = TestClient(csp_app)
        client.get("/")
        nonce = SEEN["nonce"]
        client.get("/")
        assert SEEN["nonce"] != nonce

    def test_a_page_that_does_not_ask_for_it_sets_no_cookie(self, csp_app):
        resp = TestClient(csp_app).get("/plain")
        assert "set-cookie" not in resp.headers

    def test_without_cookies_the_nonce_is_not_kept(self, csp_app):
        resp = TestClient(csp_app).get("/no-cookies")
        assert len(resp.body) >= 16
        assert "set-cookie" not in resp.headers
