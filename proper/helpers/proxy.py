"""Internal class to proxy the context variables
for the request and response objects
"""
from typing import Any, Callable, List


__all__ = ("Proxy", )


WRAPPED_FUNC = "__wrapped_func__"


class Proxy:
    __slots__ = [WRAPPED_FUNC]

    @property
    def __wrapped__(self) -> "Any":
        return self.__wrapped_func__()

    @property
    def __doc__(self) -> str:
        return self.__wrapped__.__doc__

    @property
    def __dict__(self) -> dict:
        """We need __dict__ to be explicit to ensure that
        `vars()` works as expected."""
        return self.__wrapped__.__dict__

    def __init__(self, wrapped_func: "Callable") -> None:
        object.__setattr__(self, WRAPPED_FUNC, wrapped_func)

    @property
    def __name__(self) -> str:
        return self.__wrapped__.__name__

    @property
    def __class__(self) -> "Any":
        return self.__wrapped__.__class__

    def __setattr__(self, name: str, value: "Any") -> None:
        if name == WRAPPED_FUNC:
            object.__setattr__(self, name, value)
        else:
            setattr(self.__wrapped__, name, value)

    def __getattr__(self, name: str) -> "Any":
        return getattr(self.__wrapped__, name)

    def __dir__(self) -> "List":
        return dir(self.__wrapped__)

    def __str__(self) -> str:
        return str(self.__wrapped__)

    def __repr__(self) -> str:
        return repr(self.__wrapped__)

    def __hash__(self) -> "Any":
        return hash(self.__wrapped__)

    def __nonzero__(self) -> bool:
        return bool(self.__wrapped__)

    def __bool__(self) -> bool:
        return bool(self.__wrapped__)

    def __eq__(self, other: "Any") -> bool:
        return self.__wrapped__.__eq__(other)
