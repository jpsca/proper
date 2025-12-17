from contextvars import ContextVar
from typing import Any


class GlobalContext:
    def __init__(self) -> None:
        cv = ContextVar("_current")
        cv.set({})
        super().__setattr__("_current", cv)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__getattribute__("_current").get()[name] = value

    def __getattr__(self, name: str) -> Any:
        return super().__getattribute__("_current").get().get(name)


current = GlobalContext()

