from unittest.mock import MagicMock

import pytest

from proper import Request, Response, current
from proper.concerns import (
    CSRF_FORM_KEY,
    CSRF_HEADER,
    CSRF_SESSION_KEY,
    CSRF_TOKEN_LENGTH,
    CurrentLocale,
    CurrentTimezone,
    OriginProtection,
    RateLimiting,
    RequestForgeryProtection,
)
from proper.concerns.concern import Concern
from proper.constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY
from proper.controller import Controller
from proper.errors import (
    InvalidCSRFToken,
    InvalidOrigin,
    MissingCSRFToken,
    TooManyRequests,
)
from proper.helpers import MultiDict
from proper.request.utils import make_test_scope


# ── Helpers ──────────────────────────────────────────────────────────

def _make(cls, app, **scope_kw):
    scope = make_test_scope(**scope_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return cls(request, response)


# ── Concern base class ───────────────────────────────────────────────

class TestConcernBase:
    def test_default_etag(self):
        assert Concern.etag == ""

    def test_type_annotations_exist(self):
        annotations = Concern.__annotations__
        assert "params" in annotations
        assert "defaults" in annotations
        assert "app" in annotations
        assert "request" in annotations
        assert "response" in annotations
        assert "_should_run_callback" in annotations


# ── OriginProtection ─────────────────────────────────────────────────

class OriginCtrl(OriginProtection, Controller):
    def action(self):
        return "OK"


class TestOriginProtection:
    @pytest.mark.parametrize("method", [GET, HEAD, OPTIONS, QUERY])
    def test_safe_methods_allowed(self, app, method):
        co = _make(OriginCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_no_headers_allowed(self, app, method):
        co = _make(OriginCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_trusted_origin_allowed(self, app, method):
        co = _make(OriginCtrl, app)
        co.app.config["TRUSTED_ORIGINS"] = ["https://trusted.com"]
        co.request.method = method
        co.request.matched_action = "action"
        co.request.headers["origin"] = "https://trusted.com"
        co._dispatch("action")

    @pytest.mark.parametrize("value", ["same-origin", "none"])
    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_sec_fetch_site_same_origin_allowed(self, app, value, method):
        co = _make(OriginCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        co.request.headers["sec-fetch-site"] = value
        co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_matching_origin_and_host_allowed(self, app, method):
        co = _make(OriginCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        co.request.host = "example.com"
        co.request.port = 8080
        co.request.headers["origin"] = "example.com:8080"
        co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_invalid_origin_rejected(self, app, method):
        co = _make(OriginCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        co.request.host = "example.com"
        co.request.port = 443
        co.request.headers["origin"] = "https://evil.com"
        with pytest.raises(InvalidOrigin):
            co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_cross_site_rejected(self, app, method):
        co = _make(OriginCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        co.request.headers["sec-fetch-site"] = "cross-site"
        with pytest.raises(InvalidOrigin):
            co._dispatch("action")


# ── Legacy RequestForgeryProtection ─────────────────────────────────────────

class CsrfCtrl(RequestForgeryProtection, Controller):
    def action(self):
        return "STOP"


class TestRequestForgeryProtection:
    def test_get_generates_token(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")

        csrf_token = current.csrf_token
        assert csrf_token is not None
        assert len(csrf_token) == CSRF_TOKEN_LENGTH * 2
        assert csrf_token == co.response.headers.get(CSRF_HEADER)
        assert csrf_token[CSRF_TOKEN_LENGTH:] == co.response.session[CSRF_SESSION_KEY]

    def test_missing_csrf_raises(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = POST
        co.request.matched_action = "action"
        co.request.session = {CSRF_SESSION_KEY: "a" * CSRF_TOKEN_LENGTH}
        with pytest.raises(MissingCSRFToken):
            co._dispatch("action")

    def test_missing_csrf_error_message(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = POST
        co.request.matched_action = "action"
        co.request.session = {CSRF_SESSION_KEY: "a" * CSRF_TOKEN_LENGTH}
        with pytest.raises(MissingCSRFToken, match="csrf_token"):
            co._dispatch("action")

    def test_invalid_csrf_if_no_session_token(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = POST
        co.request.matched_action = "action"
        co.request.session = {}
        with pytest.raises(InvalidCSRFToken):
            co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_valid_csrf_from_form(self, app, method):
        co = _make(CsrfCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        mask = "x" * CSRF_TOKEN_LENGTH
        token = "a" * CSRF_TOKEN_LENGTH
        co.request.session = {CSRF_SESSION_KEY: token}
        co.request.form = MultiDict({CSRF_FORM_KEY: mask + token})
        co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_invalid_csrf_from_form(self, app, method):
        co = _make(CsrfCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        mask = "x" * CSRF_TOKEN_LENGTH
        token = "a" * CSRF_TOKEN_LENGTH
        bad = "b" * CSRF_TOKEN_LENGTH
        co.request.session = {CSRF_SESSION_KEY: token}
        co.request.form = MultiDict({CSRF_FORM_KEY: mask + bad})
        with pytest.raises(InvalidCSRFToken):
            co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_valid_csrf_from_header(self, app, method):
        co = _make(CsrfCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        mask = "x" * CSRF_TOKEN_LENGTH
        token = "a" * CSRF_TOKEN_LENGTH
        co.request.session = {CSRF_SESSION_KEY: token}
        co.request.headers["x-csrf-token"] = mask + token
        co._dispatch("action")

    @pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
    def test_invalid_csrf_from_header(self, app, method):
        co = _make(CsrfCtrl, app)
        co.request.method = method
        co.request.matched_action = "action"
        mask = "x" * CSRF_TOKEN_LENGTH
        token = "a" * CSRF_TOKEN_LENGTH
        bad = "b" * CSRF_TOKEN_LENGTH
        co.request.session = {CSRF_SESSION_KEY: token}
        co.request.headers["x-csrf-token"] = mask + bad
        with pytest.raises(InvalidCSRFToken):
            co._dispatch("action")

    def test_ignore_unmasked_tokens(self, app):
        co = _make(CsrfCtrl, app)
        token = "a" * CSRF_TOKEN_LENGTH
        co.request.method = POST
        co.request.matched_action = "action"
        co.request.session = {CSRF_SESSION_KEY: token}
        co.request.form = MultiDict({CSRF_FORM_KEY: token})
        with pytest.raises(MissingCSRFToken):
            co._dispatch("action")

    def test_masking_is_random(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"

        co._dispatch("action")
        token1 = current.csrf_token

        co.request.session = co.response.session.copy()
        co._dispatch("action")
        token2 = current.csrf_token

        assert token1 != token2
        assert token1[CSRF_TOKEN_LENGTH:] == token2[CSRF_TOKEN_LENGTH:]

    def test_head_does_not_generate_token(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = HEAD
        co.request.matched_action = "action"
        co.request.session = {}
        co._dispatch("action")
        # HEAD doesn't generate a new token (only GET does)
        assert CSRF_SESSION_KEY not in co.response.session

    def test_options_does_not_generate_token(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = OPTIONS
        co.request.matched_action = "action"
        co.request.session = {}
        co._dispatch("action")
        assert CSRF_SESSION_KEY not in co.response.session

    def test_get_with_existing_session_token(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        token = "b" * CSRF_TOKEN_LENGTH
        co.request.session = {CSRF_SESSION_KEY: token}
        co._dispatch("action")
        masked = current.csrf_token
        assert masked[CSRF_TOKEN_LENGTH:] == token

    def test_generate_csrf_token_length(self, app):
        co = _make(CsrfCtrl, app)
        token = co._generate_csrf_token()
        assert len(token) == CSRF_TOKEN_LENGTH

    def test_mask_unmask_roundtrip(self, app):
        co = _make(CsrfCtrl, app)
        token = "a" * CSRF_TOKEN_LENGTH
        masked = co._mask_csrf_token(token)
        assert len(masked) == CSRF_TOKEN_LENGTH * 2
        unmasked = co._unmask_csrf_token(masked)
        assert unmasked == token

    def test_csrf_token_in_form_no_form(self, app):
        co = _make(CsrfCtrl, app)
        co.request.method = GET
        assert co._csrf_token_in_form() == ""

    def test_csrf_token_in_header_missing(self, app):
        co = _make(CsrfCtrl, app)
        assert co._csrf_token_in_header() == ""


# ── RateLimiting ─────────────────────────────────────────────────────

class RateLimitCtrl(RateLimiting, Controller):
    rate_limit = {"to": 3, "within": 60}

    def action(self):
        return "OK"


class RateLimitOnlyCtrl(RateLimiting, Controller):
    rate_limit = {"to": 2, "within": 60, "only": "create"}

    def create(self):
        return "created"

    def index(self):
        return "index"


class RateLimitExcludeCtrl(RateLimiting, Controller):
    rate_limit = {"to": 2, "within": 60, "exclude": "index"}

    def create(self):
        return "created"

    def index(self):
        return "index"


class RateLimitMultiCtrl(RateLimiting, Controller):
    rate_limit = [
        {"to": 2, "within": 60, "name": "short"},
        {"to": 5, "within": 300, "name": "long"},
    ]

    def action(self):
        return "OK"


class RateLimitCallableCtrl(RateLimiting, Controller):
    rate_limit = {
        "to": lambda self: 2,
        "within": lambda self: 60,
        "by": lambda self: "custom-id",
    }

    def action(self):
        return "OK"


class RateLimitMethodCtrl(RateLimiting, Controller):
    rate_limit = {"to": "max_reqs", "within": "window"}

    def max_reqs(self):
        return 2

    def window(self):
        return 60

    def action(self):
        return "OK"


class RateLimitReactCtrl(RateLimiting, Controller):
    rate_limit = {"to": 1, "within": 60, "react_with": "handle_limited"}
    was_rate_limited = False

    def handle_limited(self):
        self.__class__.was_rate_limited = True

    def action(self):
        return "OK"


class RateLimitReactCallableCtrl(RateLimiting, Controller):
    rate_limit = {
        "to": 1,
        "within": 60,
        "react_with": lambda self: setattr(self, "_limited", True),
    }

    def action(self):
        return "OK"


class TestRateLimiting:
    def _make_rl(self, cls, app):
        co = _make(cls, app)
        co.request.method = GET
        co.request.matched_action = "action"
        co.request.scope["client"] = ("127.0.0.1", 0)
        app.cache = MagicMock()
        return co

    def test_allows_under_limit(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        app.cache.increment.return_value = 1
        co._dispatch("action")

    def test_raises_when_over_limit(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        app.cache.increment.return_value = 4
        with pytest.raises(TooManyRequests):
            co._dispatch("action")

    def test_increment_called_with_correct_args(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        app.cache.increment.return_value = 1
        co._dispatch("action")

        app.cache.increment.assert_called_once()
        args, kwargs = app.cache.increment.call_args
        key = args[0]
        assert "rate-limit" in key
        assert args[1] == 1
        assert kwargs["expires_in"] == 60

    def test_no_cache_does_nothing(self, app):
        co = _make(RateLimitCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        app.cache = None
        co._dispatch("action")  # should not raise

    def test_only_filter(self, app):
        co = _make(RateLimitOnlyCtrl, app)
        co.request.method = GET
        co.request.matched_action = "index"
        app.cache = MagicMock()
        app.cache.increment.return_value = 100
        # index is not in "only", so rate limiting shouldn't apply
        co._dispatch("index")

    def test_only_filter_applies_to_matching_action(self, app):
        co = _make(RateLimitOnlyCtrl, app)
        co.request.method = POST
        co.request.matched_action = "create"
        co.request.scope["client"] = ("127.0.0.1", 0)
        app.cache = MagicMock()
        app.cache.increment.return_value = 3
        with pytest.raises(TooManyRequests):
            co._dispatch("create")

    def test_exclude_filter(self, app):
        co = _make(RateLimitExcludeCtrl, app)
        co.request.method = GET
        co.request.matched_action = "index"
        app.cache = MagicMock()
        app.cache.increment.return_value = 100
        # index is excluded, so rate limiting shouldn't apply
        co._dispatch("index")

    def test_exclude_filter_applies_to_non_excluded(self, app):
        co = _make(RateLimitExcludeCtrl, app)
        co.request.method = POST
        co.request.matched_action = "create"
        co.request.scope["client"] = ("127.0.0.1", 0)
        app.cache = MagicMock()
        app.cache.increment.return_value = 3
        with pytest.raises(TooManyRequests):
            co._dispatch("create")

    def test_multiple_rate_limits(self, app):
        co = _make(RateLimitMultiCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        co.request.scope["client"] = ("127.0.0.1", 0)
        app.cache = MagicMock()
        app.cache.increment.return_value = 1
        co._dispatch("action")
        # Both rate limits should be checked
        assert app.cache.increment.call_count == 2

    def test_multiple_rate_limits_second_exceeds(self, app):
        co = _make(RateLimitMultiCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        co.request.scope["client"] = ("127.0.0.1", 0)
        app.cache = MagicMock()
        # First limit passes (count=1 <= to=2), second exceeds (count=6 > to=5)
        app.cache.increment.side_effect = [1, 6]
        with pytest.raises(TooManyRequests):
            co._dispatch("action")

    def test_callable_to_and_within(self, app):
        co = self._make_rl(RateLimitCallableCtrl, app)
        app.cache.increment.return_value = 3
        with pytest.raises(TooManyRequests):
            co._dispatch("action")

    def test_callable_by(self, app):
        co = self._make_rl(RateLimitCallableCtrl, app)
        app.cache.increment.return_value = 1
        co._dispatch("action")
        key = app.cache.increment.call_args[0][0]
        assert "custom-id" in key

    def test_method_name_to_and_within(self, app):
        co = self._make_rl(RateLimitMethodCtrl, app)
        app.cache.increment.return_value = 3
        with pytest.raises(TooManyRequests):
            co._dispatch("action")

    def test_react_with_method(self, app):
        RateLimitReactCtrl.was_rate_limited = False
        co = self._make_rl(RateLimitReactCtrl, app)
        app.cache.increment.return_value = 2
        co._dispatch("action")
        assert RateLimitReactCtrl.was_rate_limited

    def test_react_with_callable(self, app):
        co = self._make_rl(RateLimitReactCallableCtrl, app)
        app.cache.increment.return_value = 2
        co._dispatch("action")
        assert co._limited

    def test_custom_scope(self, app):
        co = _make(RateLimitCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        co.request.scope["client"] = ("127.0.0.1", 0)
        app.cache = MagicMock()
        app.cache.increment.return_value = 1

        # Override rate_limit to include scope
        co.__class__ = type("ScopedCtrl", (RateLimitCtrl,), {
            "rate_limit": {"to": 3, "within": 60, "scope": "my-scope"},
        })
        co._dispatch("action")
        key = app.cache.increment.call_args[0][0]
        assert "my-scope" in key

    def test_reset_rate_limit(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        co.reset_rate_limit()
        app.cache.delete.assert_called_once()
        key = app.cache.delete.call_args[0][0]
        assert "rate-limit" in key

    def test_reset_rate_limit_custom_by(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        co.reset_rate_limit(by="user-42", scope="api", name="short")
        key = app.cache.delete.call_args[0][0]
        assert "user-42" in key
        assert "api" in key
        assert "short" in key

    def test_reset_rate_limit_no_cache(self, app):
        co = _make(RateLimitCtrl, app)
        app.cache = None
        co.reset_rate_limit()  # should not raise

    def test_count_at_exactly_limit(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        app.cache.increment.return_value = 3  # exactly at limit (to=3)
        co._dispatch("action")  # should NOT raise

    def test_count_one_over_limit(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        app.cache.increment.return_value = 4  # one over (to=3)
        with pytest.raises(TooManyRequests):
            co._dispatch("action")

    def test_increment_returns_none(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        app.cache.increment.return_value = None
        co._dispatch("action")  # should not raise

    def test_get_value_none(self, app):
        co = self._make_rl(RateLimitCtrl, app)
        assert co._RateLimiting__get_value(None) is None

    def test_no_rate_limit_attr(self, app):
        """Controller with RateLimiting mixin but no rate_limit attribute."""
        class NoLimitCtrl(RateLimiting, Controller):
            def action(self):
                return "OK"
        co = _make(NoLimitCtrl, app)
        co.request.method = GET
        co.request.matched_action = "action"
        app.cache = MagicMock()
        co._dispatch("action")
        app.cache.increment.assert_not_called()


# ── CurrentLocale ────────────────────────────────────────────────────

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


# ── CurrentTimezone ──────────────────────────────────────────────────

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
        co = _make(TzCtrl, app, url="/?timezone=US/Eastern", headers=[("cookie", "timezone=US/Pacific")])
        co.request.method = GET
        co.request.matched_action = "action"
        co._dispatch("action")
        assert current.timezone == "US/Eastern"
