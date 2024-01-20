import typing as t
from wsgiref.types import StartResponse as TStartResponse  # noqa
from wsgiref.types import WSGIEnvironment as TWSGIEnvironment  # noqa


TBody = list[bytes] | bytearray | memoryview | t.Iterable[bytes]

TException = t.Type[BaseException]
TEventHandler = t.Callable[[], None]
TEventHandlers = tuple[TEventHandler, ...]
