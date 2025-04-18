import typing as t
from collections.abc import Iterable as TIterable  # noqa
from wsgiref.types import StartResponse as TStartResponse  # noqa
from wsgiref.types import WSGIEnvironment as TWSGIEnvironment  # noqa


if t.TYPE_CHECKING:
    from proper.request.multipart import MultipartPart


TReadable = t.IO[t.Any]

TBody = bytes | bytearray | memoryview | TIterable[bytes]

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

TUpload = t.Type["MultipartPart | t.BinaryIO"]


class TAttachment:
    key: str
    service_name: str
    byte_size: int | None
    content_type: str | None
    checksum: str | None
    filename: str

    def delete_instance(self) -> None: ...
