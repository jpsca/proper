from contextvars import ContextVar
from typing import Any


class GlobalContext:
    def __init__(self) -> None:
        super().__setattr__("_vars", {})

    def __setattr__(self, name: str, value: Any) -> None:
        _vars = super().__getattribute__("_vars")
        cv = _vars.get(name)
        if cv is None:
            cv = _vars.setdefault(name, ContextVar(f"proper.current.{name}"))
        cv.set(value)

    def __getattr__(self, name: str) -> Any:
        try:
            cv = super().__getattribute__("_vars")[name]
            return cv.get()
        except (KeyError, LookupError):
            return None


current = GlobalContext()
