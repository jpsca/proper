from unittest.mock import MagicMock

from proper import Request, Response, current
from proper.concerns import CurrentLocale
from proper.constants import GET
from proper.controller import Controller
from proper.request.utils import make_test_scope


def _make(cls, app, **scope_kw):
    scope = make_test_scope(**scope_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return cls(request, response)


class LocaleCtrl(CurrentLocale, Controller):
    def action(self):
        return "OK"


class TestCurrentLocale:
    def test_sets_locale_from_params(self, app):
        co = _make(LocaleCtrl, app, url="/?locale=fr")
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")
        assert current.locale == "fr"

    def test_sets_locale_from_cookie(self, app):
        co = _make(LocaleCtrl, app, headers=[("cookie", "locale=de")])
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")
        assert current.locale == "de"

    def test_sets_locale_from_user(self, app):
        co = _make(LocaleCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        user = MagicMock()
        user.locale = "ja"
        current.user = user
        co._dispatch("action")
        assert current.locale == "ja"
        current.user = None

    def test_falls_back_to_default(self, app):
        co = _make(LocaleCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        current.user = None
        co._dispatch("action")
        assert current.locale == app.config.LOCALE_DEFAULT

    def test_etag_includes_locale(self, app):
        co = _make(LocaleCtrl, app)
        current.locale = "es"
        assert co.etag == "es"

    def test_etag_strips_leading_dash(self, app):
        co = _make(LocaleCtrl, app)
        current.locale = ""
        # When both parent etag and locale are empty, should be ""
        assert co.etag == ""

    def test_param_locale_overrides_cookie(self, app):
        co = _make(LocaleCtrl, app, url="/?locale=fr", headers=[("cookie", "locale=de")])
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")
        assert current.locale == "fr"

    def test_i18n_negotiate_locale(self, app):
        co = _make(LocaleCtrl, app, headers=[("accept-language", "pt-BR,pt;q=0.9")])
        co.request.method = GET
        co.request.matched_action = "action"
        current.user = None

        mock_i18n = MagicMock()
        mock_i18n.negotiate_locale.return_value = "pt"
        co.app.i18n = mock_i18n

        co._dispatch("action")
        assert current.locale == "pt"
