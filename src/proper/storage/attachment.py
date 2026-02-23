import hashlib
import json
import mimetypes
import typing as t
from uuid import uuid4

import peewee as pw
from inflection import parameterize

from ..errors import StorageConfigError
from ..helpers import JSONField
from .transforms import transform_image


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
        parent = pw.ForeignKeyField("self", backref="variants", null=True)
        variant_key = pw.CharField(64, default="", index=True)

        _filesto: "TUpload | None" = None

        def __init__(
            self,
            filesto: "TUpload | None" = None,
            *,
            service_name: str = "",
            filename: str = "",
            content_type: str = "",
            byte_size: int = 0,
            public: "bool | None" = None,
            parent: "t.Any" = None,
            variant_key: str = "",
            **kwargs,
        ) -> None:
            if filesto is None:
                # Loading from DB — forward all field values to peewee
                for key, val in [
                    ("service_name", service_name),
                    ("filename", filename),
                    ("content_type", content_type),
                    ("byte_size", byte_size),
                    ("public", public),
                    ("parent", parent),
                    ("variant_key", variant_key),
                ]:
                    if val:
                        kwargs[key] = val
                super().__init__(**kwargs)
                return

            super().__init__(**kwargs)
            self._filesto = filesto

            service_name = service_name or default_service_name
            if not service_name:
                raise StorageConfigError(
                    "Missing config.storage.SERVICE or service_name argument"
                )

            filename = filename or getattr(filesto, "filename", "") or ""
            if "." in filename:
                name, ext = filename.rsplit(".", 1)
                name = parameterize(name)
                ext = parameterize(ext)
                filename = f"{name}.{ext}"
            else:
                filename = parameterize(filename)

            content_type = content_type or getattr(filesto, "content_type", "") or ""
            if filename and not content_type:
                guess = mimetypes.guess_type(filename, strict=False)
                content_type = guess[0] or ""
            content_type = content_type or DEFAULT_CONTENT_TYPE

            if public is None:
                public = parent.public if parent else False

            self.service_name = service_name
            self.filename = filename or None
            self.content_type = content_type
            self.byte_size = byte_size
            self.public = public
            self.parent = parent
            self.variant_key = variant_key

        @property
        def url_for(self):
            return storage.url_for(self)

        def send_file(self):
            return storage.send_file(self)

        def save(self, force_insert: bool = False, only: "TIterable | None" = None):
            if self._filesto:
                storage.upload(self._filesto, self)
                self._filesto = None
            return super().save(force_insert=force_insert, only=only)

        SUPPORTED_VARIANT_TYPES = {
            "image/": "transform_image",
            # "video/": "transform_video",
            # "application/pdf": "transform_pdf",
        }

        @staticmethod
        def _variant_key(**transformations) -> str:
            blob = json.dumps(transformations, default=str)
            return hashlib.sha256(blob.encode()).hexdigest()

        def variant(self, **transformations):
            key = self._variant_key(**transformations)
            existing = self.__class__.get_or_none(
                self.__class__.parent == self,
                self.__class__.variant_key == key,
            )
            if existing:
                return existing

            for prefix, method_name in self.SUPPORTED_VARIANT_TYPES.items():
                if self.content_type.startswith(prefix):
                    method = getattr(self, method_name)
                    filesto = method(self.download(), **transformations)
                    return self.create_variant(
                        filesto,
                        variant_key=key,
                        metadata={"transformations": transformations},
                    )

            raise ValueError(
                f"Variants are not supported for content type '{self.content_type}'"
            )

        def transform_image(self, source, **transformations):
            return transform_image(source, **transformations)

        def create_variant(self, filesto: "TUpload", **kwargs):
            kwargs.setdefault("service_name", self.service_name)
            kwargs.setdefault("public", self.public)
            v = self.__class__(filesto, parent=self, **kwargs)
            v.save(force_insert=True)
            return v

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
