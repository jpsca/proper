import typing as t
from collections.abc import (
    Awaitable,
    Callable,
    Iterable,
    MutableMapping,
)


if t.TYPE_CHECKING:
    import datetime
    from uuid import UUID

    import peewee as pw

    from proper.request.formparser import MultipartPart


TScope = MutableMapping[str, t.Any]
TReceive = Callable[[], Awaitable[dict[str, t.Any]]]
TSend = Callable[[dict[str, t.Any]], Awaitable[None]]

TReadable = t.IO[t.Any]
TBody = bytes | bytearray | memoryview | Iterable[bytes]
TException = type[BaseException]
TEventHandler = Callable[[], t.Any]
TEventHandlers = tuple[TEventHandler, ...]


@t.runtime_checkable
class THandler(t.Protocol):
    __qualname__: str
    __module__: str

    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any: ...


TPwWalCheckpoint = t.Literal["passive", "full", "restart", "truncate"]

TPwSyncMode = t.Literal["extra", "full", "normal", "off"]

TPwJournalMode = t.Literal["delete", "truncate", "persist", "memory", "wal", "off"]

TUpload: t.TypeAlias = "MultipartPart | t.BinaryIO"


if t.TYPE_CHECKING:

    class TAttachment(pw.Model):
        """Type stub for the class returned by `attachment_for(...)`.

        Not a runtime class; gated under `TYPE_CHECKING`. Consumers see
        this as the supertype of any `Attachment` subclass built via
        `app.attachment_for(BaseModel)`. Inheriting from `pw.Model` means
        peewee query/persistence methods (`select`, `delete_instance`,
        `get_or_none`, …) are also visible to type checkers.
        """

        id: UUID
        service_name: str
        filename: str
        content_type: str
        byte_size: int
        public: bool
        created_at: datetime.datetime
        metadata: dict[str, t.Any] | None
        parent: "TAttachment | None"
        variant_key: str
        variants: Iterable["TAttachment"]

        SUPPORTED_VARIANT_TYPES: t.ClassVar[dict[str, str]]

        def __init__(
            self,
            upload: "TUpload | None" = None,
            *,
            service_name: str = "",
            filename: str = "",
            content_type: str = "",
            byte_size: int = 0,
            public: bool | None = None,
            parent: "TAttachment | None" = None,
            variant_key: str = "",
            **kwargs: t.Any,
        ) -> None: ...

        @property
        def url(self) -> str: ...

        def save(  # type: ignore[override]
            self,
            force_insert: bool = False,
            only: "Iterable | None" = None,
        ) -> int: ...

        def send_file(self) -> None: ...
        def download(self) -> bytes: ...
        def purge(self) -> None: ...
        def purge_later(self) -> None: ...
        def purge_variants(self) -> None: ...
        def purge_variants_later(self) -> None: ...
        def variant(self, **ops: t.Any) -> "TAttachment": ...
        def create_variant(
            self, upload: "TUpload", **kwargs: t.Any
        ) -> "TAttachment": ...
        def transform_image(
            self, source: "bytes | str", **ops: t.Any
        ) -> bytes: ...

        @classmethod
        def get_public(cls, pk: str) -> "TAttachment | None": ...

        @classmethod
        def get_signed(
            cls, token: str, *, max_age: int | None = None
        ) -> "TAttachment | None": ...
