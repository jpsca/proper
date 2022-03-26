"""Internal class to proxy the context variables
for the request and response objects
"""

__all__ = ("Proxy", )


WRAPPED_FUNC = "__wrapped_func__"


class Proxy:
    __slots__ = [WRAPPED_FUNC]

    @property
    def __wrapped__(self):
        return self.__wrapped_func__()

    @property
    def __doc__(self):
        return self.__wrapped__.__doc__

    @property
    def __dict__(self):
        """We need __dict__ to be explicit to ensure that
        `vars()` works as expected."""
        return self.__wrapped__.__dict__

    def __init__(self, wrapped_func):
        object.__setattr__(self, WRAPPED_FUNC, wrapped_func)

    @property
    def __name__(self):
        return self.__wrapped__.__name__

    @property
    def __class__(self):
        return self.__wrapped__.__class__

    def __setattr__(self, name, value):
        if name == WRAPPED_FUNC:
            object.__setattr__(self, name, value)
        else:
            setattr(self.__wrapped__, name, value)

    def __getattr__(self, name):
        return getattr(self.__wrapped__, name)

    def __dir__(self):
        return dir(self.__wrapped__)

    def __str__(self):
        return str(self.__wrapped__)

    def __repr__(self):
        return repr(self.__wrapped__)

    def __hash__(self):
        return hash(self.__wrapped__)

    def __nonzero__(self):
        return bool(self.__wrapped__)

    def __bool__(self):
        return bool(self.__wrapped__)

    def __eq__(self):
        return dir(self.__wrapped__)
