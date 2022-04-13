from typing import TYPE_CHECKING

from sqlalchemy import insert

from . import services
from .attachment import Attachment, AttachmentList

if TYPE_CHECKING:
    from proper import App
    from .attachment import BaseAttachment
    from .blob import Blob
    from .services import BaseService


__all__ = ("Storage",)


class Storage:
    __slots__ = ["app", "config"]

    def __init__(self, app: "App", config) -> None:
        self.app = app
        self.config = config

    def attach_one(self, service="") -> Attachment:
        service_name = service or self.config.service
        service = self.get_service(service_name)
        return Attachment(
            storage=self,
            service_name=service_name,
            service=service,
        )

    def attach_many(self, service="") -> AttachmentList:
        service_name = service or self.config.service
        service = self.get_service(service_name)
        return AttachmentList(
            storage=self,
            service_name=service_name,
            service=service,
        )

    def get_service(self, service_name: str) -> "BaseService":
        service_config = self.config[service_name]
        service_config_name = service_config.service.capitalize()
        service_cls_name = f"{service_config_name}Service"
        service_cls = getattr(services, service_cls_name)
        return service_cls(self.app, **service_config)

    def save(
        self, attachment: "BaseAttachment", blob: "Blob", analize=False
    ) -> None:
        blob.id = self.insert_blob(blob)
        self.insert_attachment(attachment, blob)
        self.app.db.s.commit()
        if analize:
            self.analize_later(blob.id)

    def insert_blob(self, blob: "Blob") -> None:
        table = self.app.db.registry.metadata.tables["storage_blobs"]
        stmt = insert(table).values(
            key=blob.key,
            service_name=blob.service_name,
            byte_size=blob.byte_size,
            content_type=blob.content_type,
            checksum=blob.checksum,
            data=blob.data,
        )
        result = self.app.db.s.execute(stmt)
        return result.inserted_primary_key[0]

    def insert_attachment(self, attachment: "BaseAttachment", blob: "Blob") -> None:
        table = self.app.db.registry.metadata.tables["storage_attachments"]
        stmt = insert(table).values(
            model_type=attachment.model_type,
            column_name=attachment.column_name,
            model_id=attachment.model_id,
            blob_id=blob.id,
            filename=blob.filename,
        )
        result = self.app.db.s.execute(stmt)
        return result.inserted_primary_key[0]

    def analize_later(self, blob_id: int) -> None:
        # ???
        self.app.scheduler.task(self.analyze)(blob_id=blob_id)

    def analyze(self, blob_id: int) -> None:
        pass
