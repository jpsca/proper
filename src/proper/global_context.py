import typing as t
from contextvars import ContextVar


if t.TYPE_CHECKING:
    from .app import App
    from .core.request import Request
    from .core.response import Response


ALWAYS_VALID = (
    "locale",
    "timezone",
    "user",
    "auth_session",
)

class GlobalContext:
    app: "App"
    request: "Request"
    response: "Response"

    _vars: dict[str, ContextVar]

    def __init__(self) -> None:
        # The three set on every request exist from the start; others are
        # made on first use.
        super().__setattr__("_vars", {
            name: ContextVar(f"proper.current.{name}")
            for name in ("app", "request", "response")
        })

    def __setattr__(self, name: str, value: t.Any) -> None:
        # `_vars` is a real attribute, so this is a plain lookup; only
        # names that are not attributes reach `__getattr__`.
        _vars = self._vars
        try:
            cv = _vars[name]
        except KeyError:
            cv = _vars.setdefault(name, ContextVar(f"proper.current.{name}"))
        cv.set(value)

    def __getattr__(self, name: str) -> t.Any:
        _vars = self._vars
        if name not in _vars:
            if name in ALWAYS_VALID:
                return None
            raise AttributeError(f"'current' has no attribute {name!r}")
        try:
            return _vars[name].get()
        except LookupError:
            return None


current = GlobalContext()
