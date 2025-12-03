from contextvars import ContextVar
from typing import Any


class GlobalContext:
    def __init__(self) -> None:
        g = ContextVar("_g")
        g.set({})
        super().__setattr__("_g", g)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__getattribute__("_g").get()[name] = value

    def __getattr__(self, name: str) -> Any:
        return super().__getattribute__("_g").get().get(name)


g = GlobalContext()

