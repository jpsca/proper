import mimetypes
from typing import TYPE_CHECKING

from sqlalchemy import insert, select, update

from . import services
from .analyzers import ImageAnalyzerVips
from .attached import Attached, AttachedMany
from .file_data import FileData

if TYPE_CHECKING:
    from typing import Any, IO, List, Optional, Type, Union

    from image_processing import ImageProcessing
    from multipart import MultipartPart
    from proper import App, Dot

    from .analyzers import Analyzer
    from .attached import Attached
    from .services import Service

    TAnalyzer = Type[Analyzer]


__all__ = ("Storage",)
DEFAULT_CONTENT_TYPE = "application/octet-stream"


class Storage:
    __slots__ = ["app", "config", "analyzers"]

    def __init__(self, app: "App", config: "Dot") -> None:
        self.app = app
        self.config = config
        self.analyzers: "List[TAnalyzer]" = [ImageAnalyzerVips]

    @property
    def db(self):
        return self.app.db

    def attach_one(self, service_name: str = "") -> "Attached":
        return Attached(
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
        attached: "Attached",
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
        content_type = content_type or DEFAULT_CONTENT_TYPE

        # We do this first, to fail early for files that cannot be
        # analyzed because of a missing dependency, e.g.: images and libvips
        Analyzer = self.get_analyzer(content_type)

        fdata = FileData(
            service_name=attached.service_name,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
        )

        self.upload_to_service(filesto, fdata)
        self.save_to_db(attached, fdata)
        self.prepare_analysis(Analyzer, fdata)

    def get_analyzer(self, content_type: str) -> "Optional[TAnalyzer]":
        for cls in self.analyzers:
            if cls.accepts(content_type):
                return cls
        return None

    def upload_to_service(
        self, filesto: "Union[MultipartPart, IO]", fdata: "FileData"
    ) -> None:
        service = self.get_service(fdata.service_name)
        service.upload(filesto, fdata)

    def save_to_db(
        self,
        attached: "Attached",
        fdata: "FileData",
    ) -> None:
        self.insert_blob(fdata)
        self.insert_attachment(attached, fdata)

    def prepare_analysis(self, analyzer: "Analyzer", fdata: "FileData") -> None:
        if analyzer:
            if analyzer.analyze_now:
                self.analyze(fdata.id)
            else:
                self.analyze_later(fdata.id)

    def get_service(self, service_name: str) -> "Service":
        service_config = self.config[service_name]
        service_config_name = service_config.service.capitalize()
        service_cls_name = f"{service_config_name}Service"
        service_cls = getattr(services, service_cls_name)
        return service_cls(self.app, **service_config)

    def insert_blob(self, fdata: "FileData") -> None:
        db = self.db
        blobs_table = db.registry.metadata.tables["storage_blobs"]
        result = db.s.execute(
            insert(blobs_table).values(
                key=fdata.key,
                service_name=fdata.service_name,
                byte_size=fdata.byte_size,
                content_type=fdata.content_type,
                checksum=fdata.checksum,
                data=fdata.data,
            )
        )
        fdata.id = result.inserted_primary_key[0]

    def insert_attachment(self, attached: "Attached", fdata: "FileData") -> None:
        db = self.db
        attachments_table = db.registry.metadata.tables["storage_attachments"]
        db.s.execute(
            insert(attachments_table).values(
                model_type=attached.model_type,
                column_name=attached.column_name,
                model_id=attached.model_id,
                blob_id=fdata.id,
                filename=fdata.filename,
            )
        )

    def load_blob(self, blob_id: "Any") -> "FileData":
        blobs_table = self.db.registry.metadata.tables["storage_blobs"]
        row = self.db.s.execute(
            select(blobs_table)
            .where(blobs_table.c.id == blob_id)
        ).fetchone()
        return FileData(row._mapping)

    def update_blob(self, fdata: "FileData") -> None:
        blobs_table = self.db.registry.metadata.tables["storage_blobs"]
        self.db.s.execute(
            update(blobs_table)
            .where(blobs_table.c.id == fdata.id)
            .values(data=fdata.data)
        )
        self.db.s.commit()

    def analyze_later(self, blob_id: int) -> None:
        assert self.app.scheduler
        analyze = self.app.scheduler.task()(self.analyze)
        analyze(blob_id=blob_id)

    def analyze(self, blob_id: int) -> None:
        fdata = self.load_blob(blob_id)
        metadata = {}

        service = self.get_service(fdata.service_name)
        for cls in self.analyzers:
            if cls.accepts(fdata) and not cls.analyze_now:
                analyzer = cls(service, fdata)
                metadata = analyzer.get_metadata()
                break

        if not metadata:
            return

        data = fdata.data or {}
        data.update(metadata)
        data["analyzed"] = True
        fdata.data = data
        self.update_blob(fdata)

    def preview(self, blob_id: int, image_pipeline: "ImageProcessing") -> None:
        fdata = self.load_blob(blob_id)
        src_path = None

        service = self.get_service(fdata.service_name)
        for cls in self.analyzers:
            if cls.accepts(fdata) and not cls.analyze_now:
                analyzer = cls(service, fdata)
                src_path = analyzer.get_preview()
                break

        if not src_path:
            return ""

        image_pipeline.source(src_path)
        out_path = image_pipeline.save()
        # TODO

    def has_attachment(
        self, model_type: str, model_id: "Any", column_name: str
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
        self, model_type: str, model_id: "Any", column_name: str
    ) -> Any:
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
        return db.s.execute(select(btable).where(btable.c.id.in_(subq))).fetchall()

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
