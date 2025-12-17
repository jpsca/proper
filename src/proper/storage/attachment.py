import mimetypes
import typing as t
from uuid import uuid4

import peewee as pw
from inflection import parameterize

from ..errors import StorageConfigError
from ..helpers import JSONField


if t.TYPE_CHECKING:
    from ..types import TIterable, TUpload
    from .storage import Storage


DEFAULT_CONTENT_TYPE = "application/octet-stream"


def get_attachment_mixin(storage: "Storage", default_service_name: str = "") -> type[pw.Model]:
    class Attachment(pw.Model):
        id = pw.UUIDField(default=uuid4, primary_key=True)
        service_name = pw.CharField(64)
        filename = pw.CharField(255, default="")
        content_type = pw.CharField(64, default=DEFAULT_CONTENT_TYPE)
        byte_size = pw.IntegerField(default=0)
        public = pw.BooleanField(default=False)
        created_at = pw.DateTimeField(default=pw.utcnow)  # type: ignore
        metadata = JSONField(null=True)

        _filesto: "TUpload | None" = None

        def __init__(
            self,
            filesto: "TUpload",
            *,
            service_name: str = "",
            filename: str = "",
            content_type: str = "",
            byte_size: int = 0,
            public: bool = False,
            **kwargs,
        ) -> None:
            self._filesto = filesto

            service_name = service_name or default_service_name
            if not service_name:
                raise StorageConfigError(
                    "Missing config.storage.SERVICE or service_name argument"
                )

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
            content_type = content_type or DEFAULT_CONTENT_TYPE

            self.service_name = service_name
            self.filename = filename or None
            self.content_type = content_type
            self.byte_size = byte_size
            self.public = public

            super().__init__(**kwargs)

        @property
        def url_for(self):
            return storage.url_for(self)  # type: ignore

        def send_file(self):
            return storage.send_file(self)  # type: ignore

        def save(self, force_insert: bool = False, only: "TIterable | None" = None):
            if self._filesto:
                storage.upload(self._filesto, self)  # type: ignore
            return super().save(force_insert=force_insert, only=only)

        def show(self):
            return storage.show(self)  # type: ignore

        def purge(self):
            return storage.purge(self)  # type: ignore

        def purge_later(self):
            return storage.purge(self, later=True)  # type: ignore

        def purge_variants(self):
            return storage.purge_variants(self)  # type: ignore

        def purge_variants_later(self):
            return storage.purge_variants(self, later=True)  # type: ignore

        def download(self):
            return storage.download(self)  # type: ignore

    return Attachment
