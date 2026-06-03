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

    def __init__(self) -> None:
        super().__setattr__("_vars", {})

    def __setattr__(self, name: str, value: t.Any) -> None:
        _vars = super().__getattribute__("_vars")
        cv = _vars.get(name)
        if cv is None:
            cv = _vars.setdefault(name, ContextVar(f"proper.current.{name}"))
        cv.set(value)

    def __getattr__(self, name: str) -> t.Any:
        _vars = super().__getattribute__("_vars")
        if name not in _vars:
            if name in ALWAYS_VALID:
                return None
            raise AttributeError(f"'current' has no attribute {name!r}")
        try:
            return _vars[name].get()
        except LookupError:
            return None


current = GlobalContext()
