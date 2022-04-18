import mimetypes
from typing import TYPE_CHECKING

from ..blob import Blob

if TYPE_CHECKING:
    from typing import Any, IO, Union
    from multipart import MultipartPart
    from ..storage import Storage


DEFAULT_CONTENT_TYPE = "application/octet-stream"


class Attached:
    column_name: str = ""
    obj: "Any" = None

    def __init__(
        self,
        storage: "Storage",
        *,
        service_name: str,
    ) -> None:
        self.storage = storage
        self.service_name = service_name

    @property
    def model_type(self) -> str:
        if not self.obj:
            return ""
        return self.obj.__class__.__name__

    @property
    def model_id(self) -> "Union[str, int]":
        if not self.obj:
            return 0
        return self.obj.id

    @property
    def has_attachment(self) -> bool:
        return self.storage.has_attachment(
            model_type=self.model_type,
            model_id=self.model_id,
            column_name=self.column_name,
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} #{id(self)}"
            f"\n service_name: {repr(self.service_name)}"
            f"\n model_type: {repr(self.model_type)}"
            f"\n model_id: {repr(self.model_id)}"
            ">"
        )

    def attach(
        self,
        filesto: "Union[MultipartPart, IO]",
        *,
        filename: str = "",
        content_type: str = "",
        byte_size: int = 0,
    ) -> None:
        filename = filename or getattr(filesto, "filename", "")
        content_type = content_type or getattr(filesto, "content_type", "") or ""
        if filename and not content_type:
            guess = mimetypes.guess_type(filename, strict=False)
            content_type = guess[0] or ""

        blob = Blob(
            service_name=self.service_name,
            byte_size=byte_size,
            content_type=content_type or DEFAULT_CONTENT_TYPE,
        )
        self.storage.upload(
            blob=blob,
            attached=self,
            filesto=filesto,
            filename=filename,
        )

    def purge(self):
        self.storage.purge(self)

    def purge_later(self):
        self.storage.purge_later(self)

    def dettach(self):
        """Deletes the attachment without purging it, leaving
        its blob in place."""
        self.storage.dettach(self)

    def dettach_later(self):
        self.storage.dettach_later(self)

    def preview(self, **kw):
        pass
