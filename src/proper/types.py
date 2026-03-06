import datetime
import typing as t
from collections.abc import (
    Awaitable,
    Callable,
    Iterable,
    MutableMapping,
)
from uuid import UUID


if t.TYPE_CHECKING:
    from proper.request.formparser import MultipartPart


TScope = MutableMapping[str, t.Any]
TReceive = Callable[[], Awaitable[dict[str, t.Any]]]
TSend = Callable[[dict[str, t.Any]], Awaitable[None]]


TReadable = t.IO[t.Any]

TBody = bytes | bytearray | memoryview | Iterable[bytes]

TException = type[BaseException]
THandler = Callable[[t.Any], t.Any]
TEventHandler = Callable[[], t.Any]
TEventHandlers = tuple[TEventHandler, ...]


TPwWalCheckpoint = (
    t.Literal["passive"]
    | t.Literal["full"]
    | t.Literal["restart"]
    | t.Literal["truncate"]
)

TPwSyncMode = (
    t.Literal["extra"] | t.Literal["full"] | t.Literal["normal"] | t.Literal["off"]
)

TPwJournalMode = (
    t.Literal["delete"]
    | t.Literal["truncate"]
    | t.Literal["persist"]
    | t.Literal["memory"]
    | t.Literal["wal"]
    | t.Literal["off"]
)

TUpload = type["MultipartPart | t.BinaryIO"]


class TAttachment:
    id: UUID
    service_name: str
    byte_size: int
    content_type: str
    filename: str
    public: bool
    created_at: datetime.datetime
    metadata: dict[str, t.Any] | None

    def delete_instance(self) -> None: ...
