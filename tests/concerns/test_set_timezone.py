from unittest.mock import MagicMock

from proper import Request, Response, current
from proper.concerns import CurrentTimezone
from proper.constants import GET
from proper.controller import Controller
from proper.request.utils import make_test_scope


def _make(cls, app, **scope_kw):
    scope = make_test_scope(**scope_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return cls(request, response)


class TzCtrl(CurrentTimezone, Controller):
    def action(self):
        return "OK"


class TestCurrentTimezone:
    def test_sets_timezone_from_params(self, app):
        co = _make(TzCtrl, app, url="/?timezone=America/New_York")
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")
        assert current.timezone == "America/New_York"

    def test_sets_timezone_from_cookie(self, app):
        co = _make(TzCtrl, app, headers=[("cookie", "timezone=Europe/London")])
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")
        assert current.timezone == "Europe/London"

    def test_sets_timezone_from_user(self, app):
        co = _make(TzCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        user = MagicMock()
        user.timezone = "Asia/Tokyo"
        current.user = user
        co._dispatch("action")
        assert current.timezone == "Asia/Tokyo"
        current.user = None

    def test_falls_back_to_default(self, app):
        co = _make(TzCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        current.user = None
        co._dispatch("action")
        assert current.timezone == app.config.TIMEZONE_DEFAULT

    def test_etag_includes_timezone(self, app):
        co = _make(TzCtrl, app)
        current.timezone = "US/Pacific"
        assert co.etag == "US/Pacific"

    def test_etag_empty_timezone(self, app):
        co = _make(TzCtrl, app)
        current.timezone = ""
        assert co.etag == ""

    def test_param_timezone_overrides_cookie(self, app):
        co = _make(
            TzCtrl,
            app,
            url="/?timezone=US/Eastern",
            headers=[("cookie", "timezone=US/Pacific")],
        )
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")
        assert current.timezone == "US/Eastern"
