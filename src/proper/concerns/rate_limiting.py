import typing as t

from proper.errors import TooManyRequests
from proper.types import TCallable
from .concern import Concern


__all__ = ("RateLimiting", )


class RateLimiting(Concern):
    """
    Applies a rate limit to all actions or those specified by the
    filters with `only` and `ignore`.

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
    def before(self):
        options = getattr(self, "rate_limit", None)
        if options:
            for opts in make_list(options):
                self._set_rate_limit(opts.copy())

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

    def _set_rate_limit(self, options: dict[str, t.Any]) -> None:
        action = self.request.matched_action
        only = options.get("only", None)
        ignore = options.get("ignore", None)

        if only and action not in make_list(only):
            return
        if ignore and action in make_list(ignore):
            return
        self._rate_limiting(**options)

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
        to = get_int_value(self, to)
        within = get_int_value(self, within)
        by = get_str_value(self, by) if by else self.request.remote_ip
        scope = scope or self.__class__.__module__
        name = name or ""

        cache_key = ":".join(["rate-limit", scope, name, by]).strip(":")
        count = store.increment(cache_key, 1, expires_in=within)
        if count and count > to:
            if react_with:
                get_value(self, react_with)
            else:
                raise TooManyRequests()


def make_list(value: t.Any) -> list[t.Any]:
    if isinstance(value, list):
        return value
    return [value]


def get_value(
    controller: Concern,
    value: t.Any | TCallable[[Concern], t.Any],
) -> t.Any:
    if value is None:
        return None
    if callable(value):
        return value(controller)
    if isinstance(value, str):
        return getattr(controller, value)()
    return value


def get_int_value(
    controller: Concern,
    value: int | str | TCallable[[Concern], int],
) -> int:
    return int(get_value(controller, value))


def get_str_value(
    controller: Concern,
    value: str | TCallable[[Concern], t.Any],
) -> str:
    return str(get_value(controller, value))
