import typing as t
from wsgiref.types import StartResponse as TStartResponse  # noqa
from wsgiref.types import WSGIEnvironment as TWSGIEnvironment  # noqa


TReadable = t.IO[t.Any]

TBody = list[bytes] | bytearray | memoryview | t.Iterable[bytes]

TException = t.Type[BaseException]
THandler = t.Callable[[t.Any], t.Any]
TEventHandler = t.Callable[[], t.Any]
TEventHandlers = tuple[TEventHandler, ...]
