from unittest.mock import MagicMock

import pytest

from proper import Request, Response
from proper.concerns import RateLimiting
from proper.constants import GET, POST
from proper.controller import Controller
from proper.errors import TooManyRequests
from proper.request.utils import make_test_scope


def _make(cls, app, **scope_kw):
    scope = make_test_scope(**scope_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return cls(request, response)


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
        co.__class__ = type(
            "ScopedCtrl",
            (RateLimitCtrl,),
            {
                "rate_limit": {"to": 3, "within": 60, "scope": "my-scope"},
            },
        )
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
