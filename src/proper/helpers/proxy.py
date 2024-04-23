"""Internal class to proxy the context variables
for the request and response objects
"""
from contextvars import ContextVar
from typing import Any


__all__ = ("Proxy", )


class Proxy:
    __slots__ = ["__contextvar__"]

    def __init__(self, contextvar: ContextVar) -> None:
        object.__setattr__(self, "__contextvar__", contextvar)

    @property
    def __wrapped__(self) -> Any:
        return self.__contextvar__.get()

    @property
    def __module__(self) -> str:  # type: ignore
        return self.__wrapped__.__module__

    @property
    def __doc__(self) -> str | None:  # type: ignore
        return self.__wrapped__.__doc__

    @property
    def __dict__(self) -> dict[str, Any]:  # type: ignore
        """We need __dict__ to be explicit to ensure that
        `vars()` works as expected."""
        return self.__wrapped__.__dict__

    @property
    def __name__(self) -> str:
        return self.__wrapped__.__name__

    @property
    def __class__(self) -> Any:
        return self.__wrapped__.__class__

    @__class__.setter
    def __class__(self, value: Any) -> None:
        self.__wrapped__.__class__ = value

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "__contextvar__":
            setattr(object, name, value)
        else:
            setattr(self.__wrapped__, name, value)

    def __getattr__(self, name: str) -> Any:
        obj = self.__wrapped__
        return obj.__getattribute__(name)

    def __contains__(self, value: Any) -> bool:
        return value in self.__wrapped__

    def __dir__(self) -> list:
        return dir(self.__wrapped__)

    def __str__(self) -> str:
        return str(self.__wrapped__)

    def __repr__(self) -> str:
        return repr(self.__wrapped__)

    def __hash__(self) -> Any:
        return hash(self.__wrapped__)

    def __nonzero__(self) -> bool:
        return bool(self.__wrapped__)

    def __bool__(self) -> bool:
        return bool(self.__wrapped__)

    def __eq__(self, other: Any) -> bool:
        return self.__wrapped__.__eq__(other)

    def _set(self, value: Any) -> None:
        self.__contextvar__.set(value)
