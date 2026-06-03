import typing as t
from collections.abc import (
    Awaitable,
    Callable,
    Iterable,
    MutableMapping,
)


if t.TYPE_CHECKING:

    from proper.core.request.formparser import MultipartPart


TScope = MutableMapping[str, t.Any]
TReceive = Callable[[], Awaitable[dict[str, t.Any]]]
TSend = Callable[[dict[str, t.Any]], Awaitable[None]]

TReadable = t.IO[t.Any]
TBody = bytes | bytearray | memoryview | Iterable[bytes]
TException = type[BaseException]


@t.runtime_checkable
class THandler(t.Protocol):
    __qualname__: str
    __module__: str

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any: ...


TPwWalCheckpoint = t.Literal["passive", "full", "restart", "truncate"]

TPwSyncMode = t.Literal["extra", "full", "normal", "off"]

TPwJournalMode = t.Literal["delete", "truncate", "persist", "memory", "wal", "off"]

TUpload: t.TypeAlias = "MultipartPart | t.BinaryIO"
