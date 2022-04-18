from typing import TYPE_CHECKING

from sqlalchemy import insert, select

from . import services
from .analyzers import ImageAnalyzerVips
from .attached.one import AttachedOne
from .attached.many import AttachedMany
from .blob import Blob

if TYPE_CHECKING:
    from typing import IO, List, Optional, Type, Union
    from multipart import MultipartPart
    from proper import App, Dot
    from .analyzers import Analyzer
    from .attached import Attached
    from .services import Service
    TAnalyzer = Type[Analyzer]


__all__ = ("Storage",)


class Storage:
    __slots__ = ["app", "config", "analyzers"]

    def __init__(self, app: "App", config: "Dot") -> None:
        self.app = app
        self.config = config
        self.analyzers: "List[TAnalyzer]" = [ImageAnalyzerVips]

    @property
    def db(self):
        return self.app.db

    def attach_one(self, service_name: str = "") -> "AttachedOne":
        return AttachedOne(
            storage=self,
            service_name=service_name or self.config.service,
        )

    def attach_many(self, service_name: str = "") -> "AttachedMany":
        return AttachedMany(
            storage=self,
            service_name=service_name or self.config.service,
        )

    def upload(
        self,
        *,
        blob: "Blob",
        attached: "Attached",
        filesto: "Union[MultipartPart, IO]",
        filename: str,
    ) -> None:
        # We do this first, to fail early for files that cannot be
        # analyzed because of a missing dependency, e.g.: images and libvips
        Analyzer = self.get_analyzer(blob)

        self.upload_to_service(filesto, attached, blob)
        self.save_to_db(attached, blob, filename)

        self.prepare_analysis(blob, Analyzer)

    def get_analyzer(self, blob) -> "Optional[TAnalyzer]":
        for cls in self.analyzers:
            if cls.accepts(blob):
                return cls
        return None

    def upload_to_service(self, filesto, attached, blob) -> None:
        service = self.get_service(attached.service_name)
        service.upload(filesto, blob)

    def save_to_db(self, attached, blob, filename) -> None:
        self.insert_blob(blob)
        self.insert_attachment(attached, blob.id, filename)

    def prepare_analysis(self, blob, analyzer) -> None:
        if analyzer:
            if analyzer.analyze_now:
                self.analyze(blob.id)
            else:
                self.analyze_later(blob.id)

    def get_service(self, service_name: str) -> "Service":
        service_config = self.config[service_name]
        service_config_name = service_config.service.capitalize()
        service_cls_name = f"{service_config_name}Service"
        service_cls = getattr(services, service_cls_name)
        return service_cls(self.app, **service_config)

    def insert_blob(self, blob: "Blob") -> None:
        db = self.db
        blobs_table = db.registry.metadata.tables["storage_blobs"]
        result = db.s.execute(
            insert(blobs_table).values(
                key=blob.key,
                service_name=blob.service_name,
                byte_size=blob.byte_size,
                content_type=blob.content_type,
                checksum=blob.checksum,
                data=blob.data,
            )
        )
        blob.id = result.inserted_primary_key[0]

    def insert_attachment(
        self, attached: "Attached", blob_id: int, filename: str
    ) -> None:
        db = self.db
        attachments_table = db.registry.metadata.tables["storage_attachments"]
        db.s.execute(
            insert(attachments_table).values(
                model_type=attached.model_type,
                column_name=attached.column_name,
                model_id=attached.model_id,
                blob_id=blob_id,
                filename=filename,
            )
        )

    def analyze_later(self, blob_id: int) -> None:
        assert self.app.scheduler
        analyze = self.app.scheduler.task()(self.analyze)
        analyze(blob_id=blob_id)

    def analyze(self, blob_id: int) -> None:
        blob = Blob()
        blob.load_from_db(self.db, blob_id)
        metadata = {}

        service = self.get_service(blob.service_name)
        for cls in self.analyzers:
            if cls.accepts(blob) and not cls.analyze_now:
                analyzer = cls(service, blob)
                metadata = analyzer.get_metadata()
                break

        if not metadata:
            return

        data = blob.data or {}
        data.update(metadata)
        data["analyzed"] = True
        blob.data = data
        blob.save_to_db(self.db)

    def has_attachment(
        self, model_type: str, model_id: "Union[str, int]", column_name: str
    ) -> bool:
        db = self.db
        table = db.registry.metadata.tables["storage_attachments"]
        count = db.s.execute(
            select(db.func.count(table.c.id))
            .where(table.c.model_type == model_type)
            .where(table.c.column_name == column_name)
            .where(table.c.model_id == model_id)
        ).scalar()
        return count > 0

    def get_blobs(
        self, model_type: str, model_id: "Union[str, int]", column_name: str
    ) -> bool:
        db = self.db
        atable = db.registry.metadata.tables["storage_attachments"]
        btable = db.registry.metadata.tables["storage_blobs"]

        subq = (
            select(atable.c.blob_id)
            .where(atable.c.model_type == model_type)
            .where(atable.c.column_name == column_name)
            .where(atable.c.model_id == model_id)
            .scalar_subquery()
        )
        return db.s.execute(
            select(btable).where(btable.c.id.in_(subq))
        ).fetchall()

    def remove_form_service(self, filesto, attached, blob) -> None:
        service = self.get_service(attached.service_name)
        service.upload(filesto, blob)

    def purge(self, attached: "Attached") -> None:
        pass

    def purge_later(self, attached: "Attached") -> None:
        pass

    def dettach(self, attached: "Attached") -> None:
        pass

    def dettach_later(self, attached: "Attached") -> None:
        pass
