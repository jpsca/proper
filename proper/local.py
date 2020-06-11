"""
The Python standard library has a concept called “thread locals” (or thread-local data).
A thread local is a global object in which you can put stuff in and get back later in a
thread-safe and thread-specific way. That means that whenever you set or get a value on
a thread local object, the thread local object checks in which thread you are and
retrieves the value corresponding to your thread (if one exists). So, you won’t
accidentally get another thread’s data.

This approach, however, has a few disadvantages. For example, besides threads, there are
other types of concurrency in Python. A very popular one is greenlets. Also, whether
every request gets its own thread is not guaranteed in WSGI. It could be that a request
is reusing a thread from a previous request, and hence data is left over in the thread
local object.

The `Local` class in this module provides a similar functionality to thread locals
but that also works with greenlets. Each thread has its own greenlet, weuse that as
the identifier for the context. If greenlets are not available we fall back to the
current thread ident.
"""
try:
    from greenlet import getcurrent as get_ident
except ImportError:
    from threading import get_ident


__all__ = ("current", )


class Local:
    __slots__ = ("__storage__", "__ident_func__")

    def __init__(self):
        object.__setattr__(self, "__storage__", {})
        object.__setattr__(self, "__ident_func__", get_ident)

    def __iter__(self):
        return iter(self.__storage__.items())

    def __getattr__(self, name):
        try:
            return self.__storage__[self.__ident_func__()][name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        ident = self.__ident_func__()
        storage = self.__storage__
        try:
            storage[ident][name] = value
        except KeyError:
            storage[ident] = {name: value}

    def __delattr__(self, name):
        try:
            del self.__storage__[self.__ident_func__()][name]
        except KeyError:
            raise AttributeError(name)

    def release(self):
        self.__storage__.pop(self.__ident_func__(), None)


current = Local()
