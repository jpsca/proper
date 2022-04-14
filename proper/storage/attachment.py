import mimetypes
from typing import TYPE_CHECKING

from .blob import Blob

if TYPE_CHECKING:
    from typing import IO, Union
    from multipart import MultipartPart
    from .services import BaseService
    from .storage import Storage


DEFAULT_CONTENT_TYPE = "application/octet-stream"


class BaseAttachment:
    __slots__ = ["storage", "service_name", "service", "column_name", "obj"]

    def __init__(
        self,
        storage: "Storage",
        *,
        service_name: str,
        service: "BaseService",
    ) -> None:
        self.storage = storage
        self.service_name = service_name
        self.service = service

        self.column_name = ""
        self.obj = None

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

    def attach(
        self,
        filesto: "Union[MultipartPart, IO]",
        *,
        filename="",
        content_type="",
        byte_size: int = 0,
        analize=True,
    ) -> None:
        blob = Blob(service_name=self.service_name)
        blob.filename = filename or getattr(filesto, "filename", "")
        blob.content_type = content_type or getattr(filesto, "content_type", None)
        if blob.filename and not blob.content_type:
            blob.content_type = mimetypes.guess_type(filename)
        blob.content_type = blob.content_type or DEFAULT_CONTENT_TYPE
        blob.byte_size = byte_size

        blob = self.service.save(filesto, blob)
        self.storage.save(attachment=self, blob=blob, analize=analize)

        if hasattr(filesto, "close"):
            filesto.close()

    def purge(self):
        pass

    def purge_later(self):
        pass

    def download(self):
        pass

    def show(self):
        pass

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        if self.obj is None:
            return f"<{cls} {self.column_name}>"
        model_id = self.obj.id
        model = self.obj.__class__.__name__
        return f"<{cls} {model}#{model_id}.{self.column_name}>"


class Attachment(BaseAttachment):
    pass


class AttachmentList(BaseAttachment):
    pass
