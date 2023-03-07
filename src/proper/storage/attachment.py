import typing as t
from datetime import datetime

from peewee import *  # noqa

if t.TYPE_CHECKING:
    from .storage import Storage
    from .types import TUpload


def get_attachment_class(storage: Storage) -> Model:
    class Attachment(storage.app.db.Model):
        key = CharField(255, index=True)
        service_name = CharField(255)
        byte_size = IntegerField()
        content_type = CharField(255)
        checksum = CharField(255, null=True)
        data = TextField(null=True)
        filename = CharField(255, null=True)
        created_at = DateTimeField(default=datetime.utcnow)

        def __init__(
            self,
            filesto: "TUpload",
            *,
            filename: str = "",
            content_type: str = "",
            byte_size: int = 0,
        ) -> None:
            self._filesto = filesto
            self.filename = filename
            self.content_type = content_type
            self.byte_size = byte_size
            super().__init__()

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
