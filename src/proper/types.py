import typing as t
from collections.abc import Iterable as TIterable  # noqa
from wsgiref.types import StartResponse as TStartResponse  # noqa
from wsgiref.types import WSGIEnvironment as TWSGIEnvironment  # noqa


TReadable = t.IO[t.Any]

TBody = list[bytes] | bytearray | memoryview | TIterable[bytes]

TException = t.Type[BaseException]
THandler = t.Callable[[t.Any], t.Any]
TEventHandler = t.Callable[[], t.Any]
TEventHandlers = tuple[TEventHandler, ...]


TPwWalCheckpoint = (
    t.Literal["passive"]
    | t.Literal["full"]
    | t.Literal["restart"]
    | t.Literal["truncate"]
)

TPwSyncMode = (
    t.Literal["extra"]
    | t.Literal["full"]
    | t.Literal["normal"]
    | t.Literal["off"]
)

TPwJournalMode = (
    t.Literal["delete"]
    | t.Literal["truncate"]
    | t.Literal["persist"]
    | t.Literal["memory"]
    | t.Literal["wal"]
    | t.Literal["off"]
)
