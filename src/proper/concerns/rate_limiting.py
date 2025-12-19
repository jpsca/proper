import typing as t

from ..errors import TooManyRequests
from ..helpers import make_list
from ..types import TCallable
from .concern import Concern


__all__ = ("RateLimiting", )


class RateLimiting(Concern):
    """
    Applies a rate limit to all actions or those specified by the
    filters with `only` and `exclude`.

    The maximum number of requests allowed is specified by `to` and constrained to
    the window of time given by `within`.

    Both `to` and `within` can be static values, method names, or callables evaluated
    within the context of the controller processing the request.

    Rate limits are by default unique to the ip address making the request, but
    you can provide your own identity function by passing a method name or a callable
    in the `by` parameter. It's evaluated within the context of the controller processing the
    request.

    By default, rate limits are scoped to the controller's path. If you want to
    share rate limits across multiple controllers, you can provide your own scope,
    by passing value in the `scope` parameter.

    Requests that exceed the rate limit will raise an `proper.error.TooManyRequests`
    error. You can specialize this by passing a method name or a callable in the `react_with`
    parameter. It's evaluated within the context of the controller processing the
    request.

    Rate limiting relies on a backing cache store.

    If you want to use multiple rate limits per controller, with the same `scope` and `by`
    values, you need to pass a list and give each of them an explicit name via the
    `name` option.

    Args:
        to:
            The maximum number of requests allowed within the time window.
        within:
            The time window in seconds.
        by:
            Optional. A method name or a callable that returns a unique identity for the requester.
            If `None`, the request's IP address is used.
        react_with:
            Optional. A method name or a callable to be invoked when the rate limit is exceeded.
            If `None`, a `proper.error.TooManyRequests` error is raised.
        scope:
            Optional. A string to identify the scope of the rate limit.
            If `None`, the controller's path is used.
        name:
            Optional. A name to identify this rate limit when multiple rate limits are defined
            for the same controller with the same `scope` and `by` values.
        only:
            Optional. An action name or a list of action names to which this rate limit applies.
            If not provided, the rate limit applies to all actions.
        exclude:
            Optional. An action name or a list of action names to which this rate limit does not
            apply. If not provided, the rate limit applies to all actions.

    Examples:

        ```python
        from proper import current
        from proper.units import SECONDS, MINUTE, MINUTES, HOUR

        class SessionsController(AppController):
            rate_limit = {"to": 10, "within": 3 * MINUTES, "only": "create"}

        class SignupsController(AppController):
            rate_limit={
                "to": 1000,
                "within": 10 * SECONDS,
                "by": lambda self: self.request.host,
                "react_with": "redirect_to_busy",
                "only": "new",
            }

            def redirect_to_busy(self):
                redirect_to(busy_controller_url, flash="Too many signups on domain!")

        class APIController(AppController):
            rate_limit = [
                {"to": 10, "within": 3 * MINUTES},
                {"to": 100, "within": 5 * MINUTES, "scope": "api_global"},
                {"to": "max_requests", "within": "time_window",
                    "by": lambda self: current.user.id},
            ]

            def max_requests(self):
                1000 if current.user.premium? else 100

            def time_window(self):
                1 * HOUR if current.user.premium? else 1 * MINUTE

        class SessionsController(AppController):
            rate_limit = [
                {"to": 3, "within": 2 * SECONDS, "name": "short-term"},
                {"to": 10, "within": 5 * MINUTES, "name": "long-term"},
            ]
        ```

    """
    before = {"do": "_set_rate_limit"}

    def reset_rate_limit(
        self,
        by: str | None = None,
        *,
        scope: str | None = None,
        name: str | None = None
    ) -> None:
        store = self.app.cache
        if not store:
            return
        by = by or self.request.remote_ip
        scope = scope or self.__class__.__module__
        name = name or ""

        cache_key = ":".join(["rate-limit", scope, name, by]).strip(":")
        store.delete(cache_key)

    def _set_rate_limit(self):
        options = getattr(self, "rate_limit", None)
        if options:
            for opts in make_list(options):
                if self._should_run_concern(opts):
                    self._rate_limiting(**opts)

    def _rate_limiting(
        self,
        *,
        to: int | str | TCallable[[Concern], int],
        within: int | str | TCallable[[Concern], int],
        by: str | TCallable[[Concern], t.Any] | None = None,
        react_with: str | TCallable[[Concern], None] | None = None,
        scope: str | None = None,
        name: str | None = None,
        **kwargs,
    ):
        store = self.app.cache
        if not store:
            return
        to = int(self.__get_value(to))
        within = int(self.__get_value(within))
        by = str(self.__get_value(by)) if by else self.request.remote_ip
        scope = scope or self.__class__.__module__
        name = name or ""

        cache_key = ":".join(["rate-limit", scope, name, by]).strip(":")
        count = store.increment(cache_key, 1, expires_in=within)
        if count and count > to:
            if react_with:
                self.__get_value(react_with)
            else:
                raise TooManyRequests()

    def __get_value(
        self,
        value: t.Any | TCallable[[Concern], t.Any],
    ) -> t.Any:
        if value is None:
            return None
        if callable(value):
            return value(self)
        if isinstance(value, str):
            return getattr(self, value)()
        return value
