from contextvars import ContextVar
from typing import Any


class GlobalContext:
    def __init__(self) -> None:
        self._g = ContextVar("_g", default=None)

    def __setattr__(self, name: str, value: Any) -> None:
        self._g.set(value)

    def __getattr__(self, name: str) -> Any:
        return self._g.get()


g = GlobalContext()

