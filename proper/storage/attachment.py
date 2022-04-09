import mimetypes
from typing import IO

from .blob import Blob


DEFAULT_CONTENT_TYPE = "application/octet-stream"


class BaseAttachment:  # noqa
    column_name = None
    obj = None

    def __init__(
        self,
        storage,
        *,
        service_name: str = "",
    ):
        self.storage = storage
        self.service_name = service_name

    @property
    def model_type(self):
        return self.obj.__clas__.__name__

    @property
    def model_id(self):
        return self.obj.id

    def attach(
        self,
        filesto: IO,
        *,
        filename: str = "",
        content_type: str = "",
        byte_size: int = 0,
        identify: bool = False,
    ):
        blob = Blob(service_name=self.service_name)
        blob.filename = filename or getattr(filesto, "filename", "")
        blob.content_type = content_type or getattr(
            filesto, "content_type", DEFAULT_CONTENT_TYPE
        )
        if blob.filename and not blob.content_type:
            blob.content_type = mimetypes.guess_type(filename)
        blob.byte_size = byte_size

        service = self.storage.get_service(self.service)
        blob = service.save(filesto, blob)
        self.storage.save(blob, identify=identify)

    def purge(self):
        pass

    def purge_later(self):
        pass

    def download(self):
        pass

    def show(self):
        pass

    def __repr__(self):
        cls = self.__class__.__name__
        if self.obj is None:
            return f"<{cls}>"
        model_id = getattr(self.obj, "id", None)
        model = self.obj.__class__.__name__
        return f"<{cls} {model}#{model_id}.{self.name}>"


class Attachment(BaseAttachment):
    pass


class AttachmentList(BaseAttachment):
    pass
