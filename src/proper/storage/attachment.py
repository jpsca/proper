import hashlib
import io
import json
import mimetypes
import typing as t
from fnmatch import fnmatch
from uuid import UUID, uuid4

import peewee as pw
from inflection import parameterize

from ..errors import StorageConfigError
from ..global_context import current
from ..helpers import JSONField
from ..units import YEAR
from .imageops import transform_image
from .services import Service


if t.TYPE_CHECKING:
    from ..app import App
    from ..types import Iterable, TAttachment, TUpload


DEFAULT_CONTENT_TYPE = "application/octet-stream"


def attachment_for(
    base_model_cls: type,
    *,
    app: "App",
    default_service_name: str = "",
) -> "type[TAttachment]":
    """Build an Attachment model class bound to `base_model_cls` (which carries
    the database) and `app` (which provides url_for / config / queue access).

    Inheriting from `base_model_cls` rather than `ProperModel` directly is what
    lets the consumer's database binding propagate without a separate `Meta`
    declaration on the user-facing class — peewee's metaclass takes `_meta`
    from the leftmost peewee-Model base.
    """

    class Attachment(base_model_cls):  # type: ignore
        # No `default=uuid4`: peewee evaluates field defaults at __init__,
        # which would populate `id` before persistence. That makes
        # `att.id` look real on an unsaved instance — and silently breaks
        # FK assignment (`book.cover = Attachment(buf)` without saving
        # would write a UUID pointing at no row). Generate the id in
        # `save()` instead so `att.id is None` truthfully signals
        # "not persisted yet."
        id: UUID = pw.UUIDField(primary_key=True)  # type: ignore
        service_name: str = pw.CharField(64)  # type: ignore
        filename: str = pw.CharField(255, default="")  # type: ignore
        content_type: str = pw.CharField(64, default=DEFAULT_CONTENT_TYPE)  # type: ignore
        byte_size: int = pw.IntegerField(default=0)  # type: ignore
        created_at = pw.DateTimeField(default=pw.utcnow)  # type: ignore
        metadata = JSONField(null=True)
        parent = pw.ForeignKeyField("self", backref="variants", null=True)
        variant_key: str = pw.CharField(64, default="", index=True)  # type: ignore
        # Where this attachment came from. "direct" = uploaded as part of
        # a form submission (the historical default). Addons may use other
        # values to mark uploads with their own lifecycle policy.
        source: str = pw.CharField(32, default="direct", index=True)  # type: ignore
        # True when the upload exists but no parent record has confirmed
        # ownership yet. Addons that pre-upload (e.g. rich-text editors
        # uploading before form submit) set this to True and a sweep task
        # purges rows that stay pending past a grace period.
        pending: bool = pw.BooleanField(default=False)  # type: ignore

        # Service-instance cache (was Storage._services). Lives on the class
        # so all instances of this Attachment share lookups.
        _services: t.ClassVar[dict[str, Service]] = {}

        _upload: "TUpload | None" = None

        SUPPORTED_VARIANT_TYPES = {
            "image/*": "transform_image",
            # "video/*": "transform_video",
            # "application/pdf": "transform_pdf",
        }

        def __init__(
            self,
            upload: "TUpload | None" = None,
            *,
            service_name: str = "",
            filename: str = "",
            content_type: str = "",
            byte_size: int = 0,
            parent: "t.Any" = None,
            variant_key: str = "",
            **kwargs,
        ) -> None:
            if upload is None:
                # Loading from DB — forward all field values to peewee
                for key, val in [
                    ("service_name", service_name),
                    ("filename", filename),
                    ("content_type", content_type),
                    ("byte_size", byte_size),
                    ("parent", parent),
                    ("variant_key", variant_key),
                ]:
                    if val is not None:
                        kwargs[key] = val
                super().__init__(**kwargs)
                return

            super().__init__(**kwargs)
            self._upload = upload

            service_name = service_name or default_service_name
            if not service_name:
                raise StorageConfigError(
                    "Missing config.storage.SERVICE or service_name argument"
                )

            filename = filename or getattr(upload, "filename", "") or ""
            if "." in filename:
                name, ext = filename.rsplit(".", 1)
                name = parameterize(name)
                ext = parameterize(ext)
                filename = f"{name}.{ext}"
            else:
                filename = parameterize(filename)

            content_type = content_type or getattr(upload, "content_type", "") or ""
            if filename and not content_type:
                guess = mimetypes.guess_type(filename, strict=False)
                content_type = guess[0] or ""
            content_type = content_type or DEFAULT_CONTENT_TYPE

            self.service_name = service_name
            self.filename = filename or ""
            self.content_type = content_type
            self.byte_size = byte_size
            self.parent = parent
            self.variant_key = variant_key

        # ── persistence ─────────────────────────────────────────────────

        def save(self, force_insert: bool = False, only: "Iterable | None" = None):
            if self._upload:
                # Fresh instance: generate the PK now (the field intentionally
                # has no `default=uuid4` so `att.id` is None until this point —
                # see the field declaration above for rationale).
                if not self.id:
                    self.id = uuid4()
                self._service.upload(self._upload, self)
                self._upload = None
                # We just populated the PK ourselves, so peewee would otherwise
                # try an UPDATE (PK is set, not force_insert) that matches zero
                # rows and silently no-op. Force the INSERT.
                force_insert = True
            return super().save(force_insert=force_insert, only=only)

        # ── URLs & serving ──────────────────────────────────────────────

        @property
        def url(self) -> str:
            if self._service.public:
                return app.url_for("PublicAttachment.show", pk=self.id)
            return app.url_for("Attachment.show", token=self.generate_token())

        def send_file(self) -> None:
            inline = self._is_inline_content_type(self.content_type)
            return self._service.send_file(
                self,
                response=current.response,
                as_attachment=not inline,
            )

        def download(self) -> bytes:
            return self._service.download(self)

        # ── lookups (replace Storage.get_public_attachment / get_attachment) ──

        @classmethod
        def get_public(cls, pk: str) -> "Attachment | None":
            obj = cls.get_or_none(cls.id == pk)
            if obj is None or not obj._service.public:
                return None
            return obj

        @classmethod
        def get_signed(
            cls, token: str, max_age: "int | None" = YEAR
        ) -> "Attachment | None":
            max_age = max(max_age or 0, 0) or YEAR
            return cls.resolve_token(token, max_age=max_age)

        # ── lifecycle ───────────────────────────────────────────────────

        def purge(self) -> None:
            self._service.purge(self)
            self.purge_variants()
            self.delete_instance()

        def purge_later(self) -> None:
            type(self)._purge_by_id(str(self.id))

        def purge_variants(self) -> None:
            for variant in self.variants:
                # variants may use a different service than their parent
                variant._service.purge(variant)
                variant.delete_instance()

        def purge_variants_later(self) -> None:
            type(self)._purge_variants_by_id(str(self.id))

        # ── variants ────────────────────────────────────────────────────

        @staticmethod
        def _variant_key(**ops) -> str:
            # The order of the load and save keys *is not* relevant
            # so we sort them before hashing to avoid generating different keys
            # for the same operations
            load = json.dumps(ops.pop("load", {}), default=str, sort_keys=True)
            save = json.dumps(ops.pop("save", {}), default=str, sort_keys=True)
            ops["load"] = load
            ops["save"] = save
            # The order of the keys *is* relevant for the hash, so we don't sort them here
            blob = json.dumps(ops, default=str, sort_keys=False)
            return hashlib.sha256(blob.encode()).hexdigest()

        def variant(self, **ops):
            # Resolve the save format up-front so the variant_key reflects
            # the actual output. Explicit save.format wins; otherwise we
            # preserve the source format when it's in STORAGE_ALLOWED_VARIANTS,
            # and fall back to STORAGE_FALLBACK_FORMAT for everything else.
            save = dict(ops.get("save") or {})
            save.setdefault("format", self._default_variant_format())
            ops = {**ops, "save": save}

            key = self._variant_key(**ops)
            existing = self.__class__.get_or_none(
                self.__class__.parent == self,
                self.__class__.variant_key == key,
            )
            if existing:
                return existing

            for pattern, method_name in self.SUPPORTED_VARIANT_TYPES.items():
                if fnmatch(self.content_type, pattern):
                    method = getattr(self, method_name)
                    upload = method(self.download(), **ops)
                    if isinstance(upload, (bytes, bytearray)):
                        upload = io.BytesIO(upload)
                    ext = save["format"].lstrip(".").lower()
                    variant_filename = f"variant.{ext}"
                    variant_content_type = (
                        mimetypes.guess_type(variant_filename, strict=False)[0]
                        or self.content_type
                    )
                    return self.create_variant(
                        upload,
                        variant_key=key,
                        filename=variant_filename,
                        content_type=variant_content_type,
                        metadata={"ops": ops},
                    )

            raise ValueError(
                f"Variants are not supported for content type '{self.content_type}'"
            )

        def _default_variant_format(self) -> str:
            """Pick a save format for variants when the caller didn't specify one.

            If the source content type matches one of the patterns in
            `STORAGE_ALLOWED_VARIANTS`, preserve the source format (so a PNG
            stays a PNG, a WebP stays a WebP). Otherwise, fall back to
            `STORAGE_FALLBACK_FORMAT` (default "png").
            """
            allowed = app.config.get("STORAGE_ALLOWED_VARIANTS", ())
            fallback = app.config.get("STORAGE_FALLBACK_FORMAT", "png")
            if any(fnmatch(self.content_type, pattern) for pattern in allowed):
                ext = mimetypes.guess_extension(self.content_type, strict=False)
                if ext:
                    return ext.lstrip(".")
            return fallback

        def transform_image(self, source, **ops):
            return transform_image(source, **ops)

        def create_variant(self, upload: "TUpload", **kwargs):
            kwargs.setdefault("service_name", self.service_name)
            v = self.__class__(upload, parent=self, **kwargs)
            v.save(force_insert=True)
            return v

        # ── private ───────────────────────────────────────────────────

        @property
        def _service(self) -> Service:
            return type(self)._get_service(self.service_name)

        @classmethod
        def _get_service(cls, service_name: str) -> Service:
            """Look up (and cache) a configured Service by name.

            To add your own service, subclass `proper.storage.Service`
            implementing the required methods. Then add a config with the
            class name as the type. For example:

            ```python
            STORAGE_SERVICES = {
                "gcs": {"type": "GoogleCloud", "arg1": "value1"},
            }
            STORAGE = "gcs"
            ```
            """
            if service_name in cls._services:
                return cls._services[service_name]

            config = dict(app.config.get("STORAGE_SERVICES", {}).get(service_name, {}))
            service_type = config.pop("type", "")
            available = {c.__name__: c for c in Service.__subclasses__()}
            service_cls = available.get(service_type)
            if service_cls is None:
                raise ValueError(
                    f"Unknown service type '{service_type}' for '{service_name}'. "
                    f"Available types: {', '.join(available.keys())}"
                )
            service = service_cls(app, **config)
            cls._services[service_name] = service
            return service

        @classmethod
        def _is_inline_content_type(cls, content_type: str) -> bool:
            allowed = app.config.get("STORAGE_ALLOWED_INLINE", ())
            return any(fnmatch(content_type, pattern) for pattern in allowed)

        # ── purge-later helpers ─────────────────────────────────────────
        # These are wrapped as Huey tasks below (after the class body) so
        # registration happens in every process that imports this module —
        # web AND worker share the same TASK_REGISTRY entry. Wrapping at
        # call time would only register in the calling process, leaving the
        # worker unable to dispatch the message. The task takes just the
        # primary key; the worker re-fetches the row before acting, which
        # is safer than enqueuing a bound method on a possibly-deleted
        # instance.

        @classmethod
        def _purge_by_id(cls, pk: str) -> None:
            inst = cls.get_or_none(cls.id == pk)
            if inst:
                inst.purge()

        @classmethod
        def _purge_variants_by_id(cls, pk: str) -> None:
            inst = cls.get_or_none(cls.id == pk)
            if inst:
                inst.purge_variants()

    # Namespace task names by the base class so multiple Attachment classes
    # (e.g. distinct bases on the same app) don't collide in Huey's registry.
    # The name must be deterministic — web and worker derive the same string
    # from the same `base_model_cls`, so messages dispatched in one process
    # resolve in the other.
    task_ns = f"{base_model_cls.__module__}.{base_model_cls.__qualname__}"
    Attachment._purge_by_id = app.queue.task(name=f"{task_ns}._purge_by_id")(
        Attachment._purge_by_id
    )
    Attachment._purge_variants_by_id = app.queue.task(
        name=f"{task_ns}._purge_variants_by_id"
    )(Attachment._purge_variants_by_id)

    return t.cast("type[TAttachment]", Attachment)
