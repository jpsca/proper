import typing as t


if t.TYPE_CHECKING:
    from ..controller import Controller

    _Base = Controller
else:
    _Base = object


class Concern(_Base):
    """Base class for concerns."""
