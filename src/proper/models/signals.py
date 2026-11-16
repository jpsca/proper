"""
Model signals

Warning:
1. Signals fire only through the high-level methods (`create()`, `save()`, and `delete_instance()`).
Bulk operations via `insert()`, `update()`, and `delete()` do not trigger signals because no model
instance is involved.
2. Errors in `after_*` hooks will not prevent the main operation from completing. For example
if you add an `Event` in an `after_create` hook of a Document, and the hook raises an error,
the Document will be created, but the error will propagate and should be handled appropriately.
"""
import threading
import typing as t
from collections.abc import Callable, Iterable


class ModelSignal:
    def __init__(self):
        self._lock = threading.Lock()
        self._flush()

    def _flush(self):
        with self._lock:
            self._receivers = frozenset()
            self._receiver_list = []

    def connect(self, receiver: t.Any, *, sender: t.Any = None, is_method: bool = False):
        key = (receiver, sender)
        # `send()` reads the list without the lock, so it is replaced, never
        # changed in place.
        with self._lock:
            if key in self._receivers:
                raise ValueError(f"receiver {receiver!r} (for sender={sender or 'any'}) already connected")
            self._receivers = self._receivers | {key}
            self._receiver_list = [*self._receiver_list, (receiver, sender, is_method)]

    def disconnect(self, receiver: t.Any, *, sender: t.Any = None):
        key = (receiver, sender)
        with self._lock:
            if key not in self._receivers:
                raise ValueError(f"receiver {receiver!r} for sender={sender or 'any'} not found.")
            self._receivers = self._receivers - {key}
            self._receiver_list = [
                (r, s, m) for r, s, m in self._receiver_list
                if (r, s) != key
            ]

    def __call__[F: Callable[..., t.Any]](self, fn: F) -> F:
        # Typed as returning what it gets, so editors and type checkers keep
        # the name, the signature and the docstring of the decorated function.
        if isinstance(fn, _MethodReceiver):
            # A method decorated with more than one signal.
            fn.signals.append(self)
            return fn
        parent = fn.__qualname__.rpartition(".")[0]
        if parent and not parent.endswith("<locals>"):
            return t.cast(F, _MethodReceiver(self, fn))
        self.connect(fn)
        return fn

    def send(self, instance, *args, **kwargs):
        sender = instance if isinstance(instance, type) else type(instance)
        responses = []
        called = set()
        for r, s, is_method in self._receiver_list:
            if s is None or issubclass(sender, s):
                if is_method:
                    # The method is looked up by name, so a subclass that
                    # overrides it runs its own version, and only once even
                    # if it is decorated again.
                    fn = getattr(sender, r.__name__, r)
                    if fn in called:
                        continue
                    called.add(fn)
                    responses.append((fn, fn(instance, *args, **kwargs)))
                else:
                    responses.append((r, r(sender, instance, *args, **kwargs)))
        return responses


class _MethodReceiver:
    """Connects a method decorated with one or more signals once its class exists."""

    def __init__(self, signal: ModelSignal, fn: t.Any):
        self.signals = [signal]
        self.fn = fn

    def __set_name__(self, owner, attr):
        setattr(owner, attr, self.fn)
        for signal in self.signals:
            signal.connect(self.fn, sender=owner, is_method=True)


before_save = ModelSignal()
after_save = ModelSignal()
before_delete = ModelSignal()
after_delete = ModelSignal()
before_create = ModelSignal()
after_create = ModelSignal()


class SignalsMixin:
    def save(self, force_insert: bool = False, only: Iterable | None = None) -> int | bool:
        # A model without a primary key is always inserted.
        pk_value = self._pk if self._meta.primary_key is not False else None  # type: ignore
        created = force_insert or pk_value is None
        before_save.send(self)
        if created:
            before_create.send(self)
        ret = super().save(force_insert, only)  # type: ignore
        if created:
            after_create.send(self)
        after_save.send(self)
        return ret

    def delete_instance(self, *args, **kwargs) -> t.Any:
        before_delete.send(self)
        ret = super().delete_instance(*args, **kwargs)  # type: ignore
        after_delete.send(self)
        return ret
