import mimetypes
import typing as t
from datetime import datetime
from uuid import uuid4

from inflection import parameterize
from peewee import *  # noqa


if t.TYPE_CHECKING:
    from ..helpers import DotDict
    from .storage import Storage
    from .types import TUpload


DEFAULT_CONTENT_TYPE = "application/octet-stream"


def get_attachment_class(storage: "Storage", config: "DotDict") -> Model:
    class Attachment(storage.app.db.Model):
        key = CharField(32, primary_key=True)
        service_name = CharField(64)
        byte_size = IntegerField(default=0)
        content_type = CharField(64, default=DEFAULT_CONTENT_TYPE)
        filename = CharField(255, default="")
        checksum = CharField(128, null=True)
        created_at = DateTimeField(default=datetime.utcnow)

        def __init__(
            self,
            filesto: "TUpload",
            *,
            service_name: str = "",
            filename: str = "",
            content_type: str = "",
            byte_size: int = 0,
            **kwargs,
        ) -> None:
            self._filesto = filesto

            service_name = service_name or self.config.STORAGE or ""
            if not service_name:
                raise ValueError(
                    "Missing config.storage.service or service_name argument"
                )

            key = uuid4().hex
            filename = filename or getattr(filesto, "filename", "") or ""
            name, ext = filename.split(".", 1)
            name = parameterize(name)
            ext = parameterize(ext)
            ext = f".{ext}" if ext else ""
            filename = f"{name}{ext}"

            content_type = content_type or getattr(filesto, "content_type", "") or ""
            if filename and not content_type:
                guess = mimetypes.guess_type(filename, strict=False)
                content_type = guess[0] or ""
            content_type = content_type or self.DEFAULT_CONTENT_TYPE

            self.key = key
            self.service_name = service_name
            self.filename = filename or None
            self.content_type = content_type
            self.byte_size = byte_size

            super().__init__(**kwargs)

        @property
        def url_for(self):
            return storage.url_for(self)

        def send_file(self):
            return storage.send_file(self)

        def save(self):
            storage.upload(self._filesto, self)
            return super().save()

        def show(self):
            return storage.show(self)

        def purge(self):
            return storage.purge(self)

        def purge_later(self):
            return storage.purge(self, later=True)

        def purge_variants(self):
            return storage.purge_variants(self)

        def purge_variants_later(self):
            return storage.purge_variants(self, later=True)

        def download(self):
            return storage.download(self)

    return Attachment
