"""
minijx runtime: the `loop` object of a `{% for %}`.

Only created when the loop body mentions `loop`. Mirrors
`jinja2.runtime.LoopContext`. The compiler emits:

    loop = Loop(iterable, depth0, recurse)
    for item in loop:
        ...

`Loop.__iter__` yields the items and keeps `index0` in sync, with one item of
look-ahead so `nextitem` and `last` work on any iterable.
"""

import typing as t
from collections.abc import Sized


_MISSING = object()


class Loop:
    __slots__ = (
        "_iterator", "_prev", "_next", "_after", "_length", "_recurse", "depth0",
        "index0", "_last_changed_value",
    )

    def __init__(self, iterable: t.Iterable, depth0: int = 0, recurse: t.Callable | None = None) -> None:
        self._iterator = iter(iterable)
        self._prev = _MISSING  # the item rendered before the current one
        self._next = _MISSING  # the item currently being rendered
        self._after = _MISSING  # the one after it, already pulled
        # Known up front when the iterable has a length; otherwise `length`
        # materialises the rest on first use.
        self._length: int | None = len(iterable) if isinstance(iterable, Sized) else None
        self._recurse = recurse
        self.depth0 = depth0
        self.index0 = -1
        self._last_changed_value: t.Any = _MISSING

    def __iter__(self):
        return self

    def __next__(self):
        if self._after is _MISSING:
            self._after = self._pull()
        current = self._after
        if current is _MISSING:
            raise StopIteration
        self._after = self._pull()
        self._prev = self._next
        self._next = current
        self.index0 += 1
        return current

    def _pull(self):
        try:
            return next(self._iterator)
        except StopIteration:
            return _MISSING

    # Jinja API

    @property
    def index(self) -> int:
        return self.index0 + 1

    @property
    def depth(self) -> int:
        return self.depth0 + 1

    @property
    def first(self) -> bool:
        return self.index0 == 0

    @property
    def last(self) -> bool:
        return self._after is _MISSING

    @property
    def length(self) -> int:
        if self._length is None:
            # Materialise the rest; same trade-off as Jinja.
            rest = list(self._iterator)
            self._iterator = iter(rest)
            self._length = self.index0 + 1 + (0 if self._after is _MISSING else 1) + len(rest)
        return self._length

    @property
    def revindex(self) -> int:
        return self.length - self.index0

    @property
    def revindex0(self) -> int:
        return self.length - self.index

    @property
    def previtem(self) -> t.Any:
        return None if self._prev is _MISSING else self._prev

    @property
    def nextitem(self) -> t.Any:
        return None if self._after is _MISSING else self._after

    def cycle(self, *args: t.Any) -> t.Any:
        if not args:
            raise TypeError("no items for cycling given")
        return args[self.index0 % len(args)]

    def changed(self, *value: t.Any) -> bool:
        if self._last_changed_value != value:
            self._last_changed_value = value
            return True
        return False

    def __call__(self, iterable: t.Iterable) -> str:
        if self._recurse is None:
            raise TypeError("the loop is not recursive; add `recursive` to the for statement")
        return self._recurse(iterable, self.depth0 + 1)

    def __len__(self) -> int:
        return self.length

    def __repr__(self) -> str:
        return f"<Loop {self.index}/{self.length}>"
