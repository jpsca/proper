from typing import TYPE_CHECKING

from sqlalchemy import insert

from . import services
from .attachment import Attachment, AttachmentList

if TYPE_CHECKING:
    from proper import App
    from .attachment import BaseAttachment
    from .blob import Blob
    from .services import BaseService


__all__ = ("Storage", )


class Storage:
    def __init__(self, app: "App", **config) -> None:
        self.app = app
        self.config = config

    def attach_one(self, service: str = "") -> Attachment:
        return Attachment(storage=self, service_name=service)

    def attach_many(self, service: str = "") -> AttachmentList:
        return AttachmentList(storage=self, service_name=service)

    def get_service(self, service_name: str = "") -> "BaseService":
        service_name = service_name or self.config.storage.service
        service_config = self.config.storage[service_name]
        service_cls_name = f"{service_config.service}Service"
        service_cls = getattr(services, service_cls_name)
        return service_cls(self.app, **service_config)

    def save(self, attachment: "BaseAttachment", blob: "Blob", analize: bool = False) -> None:
        blob.id = self.insert_blob(blob)
        self.insert_attachment(attachment, blob)
        self.app.db.s.commit()
        if analize:
            self.analize_later(blob.id)

    def insert_blob(self, blob: "Blob") -> None:
        stmt = (
            insert("storage_blobs").
            values(
                key=blob.key,
                service_name=blob.service_name,
                byte_size=blob.byte_size,
                content_type=blob.content_type,
                checksum=blob.checksum,
                metadata=blob.metadata,
            )
        )
        result = self.app.db.s.execute(stmt)
        return result.inserted_primary_key[0]

    def insert_attachment(self, attachment: "BaseAttachment", blob: "Blob") -> None:
        stmt = (
            insert("storage_attachments").
            values(
                model_type=attachment.model_type,
                column_name=attachment.name,
                model_id=attachment.model_id,
                blob_id=blob.id,
                filename=blob.filename,
            )
        )
        result = self.app.db.s.execute(stmt)
        return result.inserted_primary_key[0]

    def analize_later(self, blob_id: int) -> None:
        # ???
        self.app.scheduler.task(self.analyze)(blob_id=blob_id)

    def analyze(self, blob_id: int) -> None:
        pass
