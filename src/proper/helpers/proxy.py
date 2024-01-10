"""Internal class to proxy the context variables
for the request and response objects
"""
from typing import Any, Callable


__all__ = ("Proxy", )


class Proxy:
    __slots__ = ["__wrapped_get__", "__wrapped_set__"]

    def __init__(self, wrapped_get: Callable, wrapped_set: Callable) -> None:
        object.__setattr__(self, "__wrapped_get__", wrapped_get)
        object.__setattr__(self, "__wrapped_set__", wrapped_set)

    @property
    def __wrapped__(self) -> Any:
        return self.__wrapped_get__()

    @property
    def __doc__(self) -> str:  # type: ignore
        return self.__wrapped__.__doc__ or ""

    @property
    def __dict__(self) -> dict:  # type: ignore
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
    def __class__(self, value: Any) -> None:  # noqa
        self.__wrapped__.__class__ = value

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("__wrapped_get__", "__wrapped_set__"):
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

    def _set(self, value: Any):
        return self.__wrapped_set__(value)
