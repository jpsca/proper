import datetime
import typing as t
from collections.abc import Iterable as TIterable  # noqa
from uuid import UUID
from wsgiref.types import StartResponse as TStartResponse  # noqa
from wsgiref.types import WSGIEnvironment as TWSGIEnvironment  # noqa


if t.TYPE_CHECKING:
    from proper.request.multipart import MultipartPart


TReadable = t.IO[t.Any]

TBody = bytes | bytearray | memoryview | TIterable[bytes]

TException = type[BaseException]
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
