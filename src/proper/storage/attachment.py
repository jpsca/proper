import hashlib
import io
import json
import mimetypes
import shutil
import subprocess
import typing as t
from fnmatch import fnmatch
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from uuid import uuid4

import peewee as pw
from inflection import parameterize

from ..errors import StorageConfigError
from ..global_context import current
from ..models import JSONField, ProperModel
from ..units import YEAR
from .imageops import pyvips, transform_image
from .services import Service


if t.TYPE_CHECKING:
    from datetime import datetime

    from ..app import App
    from ..types import Iterable, TUpload


DEFAULT_CONTENT_TYPE = "application/octet-stream"


class _Attachment(ProperModel):
    id: str
    service_name: str
    filename: str
    content_type: str
    byte_size: int
    created_at: "datetime"
    metadata: dict | None
    parent: t.Self | None
    variant_key: str
    # Where this attachment came from. "direct"
    # a form submission (the historical default). Addons may use other
    # values to mark uploads with their own lifecycle policy.
    source: str
    # True when the upload exists but no parent record has confirmed
    # ownership yet. Addons that pre-upload (e.g. rich-text editors
    # uploading before form submit) set this to True and a sweep task
    # purges rows that stay pending past a grace period.
    pending: bool

    _app: "App"  # set by attachment_for()
    _default_service_name: str  # set by attachment_for()

    # Service-instance cache (was Storage._services). Lives on the class
    # so all instances of this Attachment share lookups.
    _services: t.ClassVar[dict[str, Service]]

    _upload: "TUpload | None" = None

    # All of these previewers are included but each of them require extra
    # python packages and/or *system* libraries.
    #
    # Uncomment the ones you want to use and make sure to install the
    # required dependencies. Note that you can also add your own custom previewers.
    #
    # Read the storage docs for details https://properproject.org/docs/storage/.
    VARIANTS_ENABLED_FOR: dict[str, str] = {
        # Requires the `pyvips` python library and the
        # [libvips](https://www.libvips.org/install.html) system library.
        # "image/*": "preview_image",

        # Requires [poppler](https://poppler.freedesktop.org/).
        # "application/pdf": "preview_pdf",

        # Requires [ffmpeg v3.4+](https://ffmpeg.org/)
        # "video/*": "preview_video",
    }

    def __new__(cls, *args, **kwargs):
        cls._validate_previewers()
        return super().__new__(cls)

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
            # Loading from DB - forward all field values to peewee
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

        service_name = service_name or self._default_service_name
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
        self.filename = filename
        self.content_type = content_type
        self.byte_size = byte_size
        self.parent = parent
        self.variant_key = variant_key

    @property
    def service(self) -> Service:
        return type(self)._get_service(self.service_name)

    @property
    def extension(self) -> str:
        if "." in self.filename:
            return self.filename.rsplit(".", 1)[1].lower()
        return ""

    @property
    def variants(self) -> "pw.ModelSelect":
        # Query through `type(self)` so the result is bound to the leaf
        # subclass's database. A peewee `backref` would pin its `rel_model`
        # to the class that declared the FK, breaking further subclassing.
        cls = type(self)
        return cls.select().where(cls.parent == self)

    @classmethod
    def is_allowed_inline(cls, content_type: str) -> bool:
        allowed = cls._app.config.get("STORAGE_ALLOWED_INLINE", ())
        return any(fnmatch(content_type, pattern) for pattern in allowed)

    # --- Persistence ---

    @classmethod
    def create_pending_blob(
        cls,
        *,
        filename: str,
        content_type: str = "",
        byte_size: int = 0,
        service_name: str = "",
        source: str = "direct",
    ) -> t.Self:
        """Create a pending Attachment row with metadata only (no file
        bytes yet). Used by the DirectUpload protocol: the client posts
        blob metadata, we register a row + signed token, the client
        then PUTs the bytes to the token-scoped upload URL.

        The row is `pending=True` so the rich_text sweeper purges it
        if the upload never completes (tab closed mid-upload, etc.).
        """
        service_name = service_name or cls._default_service_name
        if not service_name:
            raise StorageConfigError(
                "Missing config.storage.SERVICE or service_name argument"
            )

        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            filename = f"{parameterize(name)}.{parameterize(ext)}"
        else:
            filename = parameterize(filename)

        if not content_type and filename:
            guess = mimetypes.guess_type(filename, strict=False)
            content_type = guess[0] or ""
        content_type = content_type or DEFAULT_CONTENT_TYPE

        obj = cls(
            service_name=service_name,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
        )
        obj.id = uuid4().hex
        obj.source = source
        obj.pending = True
        obj.save(force_insert=True)
        return obj

    def save(self, force_insert: bool = False, only: "Iterable | None" = None):
        if self._upload:
            # Fresh instance: generate the PK now (the field intentionally
            # has no `default=uuid4` so `att.id` is None until this point -
            # see the field declaration above for rationale).
            if not self.id:
                self.id = uuid4().hex
            self.service.upload(self._upload, self)
            self._upload = None
            # We just populated the PK ourselves, so peewee would otherwise
            # try an UPDATE (PK is set, not force_insert) that matches zero
            # rows and silently no-op. Force the INSERT.
            force_insert = True
        return super().save(force_insert=force_insert, only=only)

    # --- URLs & serving ---

    @property
    def url(self) -> str:
        """The URL for this attachment. Alias of `url_redirect`.
        """
        return self.get_redirect_url()

    def get_redirect_url(self, **kwargs) -> str:
        """Routes via `StorageRedirectController`, which redirects to the
        service's native URL when available (e.g. presigned S3 link) and
        otherwise streams the bytes."""
        return self.url_for("StorageRedirect.show", salt="redirect", **kwargs)

    def get_proxy_url(self, **kwargs) -> str:
        """Routes via `StorageProxyController`, which always streams
        the bytes through the app."""
        return self.url_for("StorageProxy.show", salt="proxy", **kwargs)

    def url_for(self, action: str, *, salt: str | None = None, **kwargs) -> str:
        """Generate a URL for this attachment using the specified action as
        salt. The action should correspond to a controller that can resolve
        the token and serve the file (e.g. "Download.show"), and the
        salt should match what that controller expects when resolving the
        token.
        """
        return self._app.url_for(
            action,
            token=self.generate_token(salt=salt),
            filename=self.filename,
            **kwargs
        )

    def service_url(self) -> "str | None":
        """The service's native URL for this attachment (e.g. a presigned
        S3 GET URL), or `None` for services that don't expose one (e.g.
        Disk). Callers should fall back to `send_file()` when this returns
        `None`.
        """
        inline = self.is_allowed_inline(self.content_type)
        return self.service.service_url(self, as_attachment=not inline)

    def send_file(self) -> None:
        inline = self.is_allowed_inline(self.content_type)
        return self.service.send_file(
            self,
            response=current.response,
            as_attachment=not inline,
        )

    def download(self) -> bytes:
        return self.service.download(self)

    # --- Lookups (replace Storage.get_public_attachment / get_attachment) ---

    @classmethod
    def get_public(cls, pk: str) -> t.Self | None:
        obj = cls.get_or_none(cls.id == pk)
        if obj is None or not obj.service.public:
            return None
        return obj

    @classmethod
    def get_signed(
        cls, token: str,
        *,
        max_age: int | None = YEAR,
        salt: str | None = None,
    ) -> t.Self | None:
        if max_age is not None:
            max_age = max(max_age, 0)
        return cls.resolve_token(token, max_age=max_age, salt=salt)

    # --- Lifecycle ---

    def purge(self) -> None:
        self.service.purge(self)
        self.purge_variants()
        self.delete_instance()

    def purge_later(self) -> None:
        type(self)._purge_by_id(str(self.id))

    def purge_variants(self) -> None:
        for variant in self.variants:
            # variants may use a different service than their parent
            variant.service.purge(variant)
            variant.delete_instance()

    def purge_variants_later(self) -> None:
        type(self)._purge_variants_by_id(str(self.id))

    # --- Variants/Previews ---

    @property
    def is_previewable(self) -> bool:
        return any(
            fnmatch(self.content_type, pattern)
            for pattern in self.VARIANTS_ENABLED_FOR.keys()
        )

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
        ops = {**ops, "save": save.copy()}

        key = self._variant_key(**ops)
        existing = self.__class__.get_or_none(
            self.__class__.parent == self,
            self.__class__.variant_key == key,
        )
        if existing:
            return existing

        for pattern, method_name in self.VARIANTS_ENABLED_FOR.items():
            if fnmatch(self.content_type, pattern):
                method = getattr(self, method_name)
                image_bytes = method(self.download(), **ops)
                image_bytes = transform_image(image_bytes, **ops)
                upload = io.BytesIO(image_bytes)

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
        allowed = self._app.config.get("STORAGE_ALLOWED_VARIANTS", ())
        fallback = self._app.config.get("STORAGE_FALLBACK_FORMAT", "png")
        if any(fnmatch(self.content_type, pattern) for pattern in allowed):
            ext = mimetypes.guess_extension(self.content_type, strict=False)
            if ext:
                return ext.lstrip(".")
        return fallback

    def create_variant(self, upload: "TUpload", **kwargs):
        kwargs.setdefault("service_name", self.service_name)
        v = self.__class__(upload, parent=self, **kwargs)
        v.save(force_insert=True)
        return v

    def preview_image(self, source: bytes, **ops) -> bytes:
        return source

    def preview_pdf(self, source: bytes, *, page: int = 1, dpi: int = 150, **ops) -> bytes:
        """Extract a page of a PDF as an image and apply any image ops.

        Requires the `pdftoppm` command from
        [poppler](https://poppler.freedesktop.org/).
        """
        tmp_pdf = None
        if isinstance(source, (bytes, bytearray)):
            tmp_pdf = NamedTemporaryFile(mode="wb+", suffix=".pdf")
            tmp_pdf.write(source)
            tmp_pdf.flush()
            input_filepath = tmp_pdf.name
        else:
            input_filepath = str(source)

        try:
            with TemporaryDirectory() as out_dir:
                out_prefix = Path(out_dir) / "page"
                subprocess.run(
                    [
                        "pdftoppm",
                        input_filepath,
                        str(out_prefix),
                        "-png",
                        "-cropbox",
                        "-f", str(page),
                        "-r", str(dpi),
                        "-singlefile",
                    ],
                    check=True,
                    capture_output=True,
                )
                image_bytes = out_prefix.with_suffix(".png").read_bytes()
        finally:
            if tmp_pdf is not None:
                tmp_pdf.close()

        return image_bytes

    def preview_video(self, source: bytes, *, at_seconds: float = 1.0, **ops) -> bytes:
        """Extract a single frame from a video as an image and apply any image ops.

        Requires the `ffmpeg` command from
        [ffmpeg v3.4+](https://ffmpeg.org/).
        """
        tmp_video = None
        if isinstance(source, (bytes, bytearray)):
            tmp_video = NamedTemporaryFile(mode="wb+")
            tmp_video.write(source)
            tmp_video.flush()
            input_filepath = tmp_video.name
        else:
            input_filepath = str(source)

        try:
            with TemporaryDirectory() as out_dir:
                out_path = Path(out_dir) / "frame.png"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-ss", str(at_seconds),
                        "-i", input_filepath,
                        "-frames:v", "1",
                        "-update", "1",
                        "-y",
                        "-loglevel", "error",
                        str(out_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                image_bytes = out_path.read_bytes()
        finally:
            if tmp_video is not None:
                tmp_video.close()

        return image_bytes

    # --- Private ---

    @classmethod
    def _validate_previewers(cls):
        if "image/*" in cls.VARIANTS_ENABLED_FOR:
            if pyvips is None:
                raise ImportError(
                    "preview_image requires the `pyvips` python library and the " \
                    "`libvips` system library." \
                    "Install libvips (https://www.libvips.org/install.html) " \
                    "and then pyvips (https://pypi.org/project/pyvips/)."
                ) from None

        if "application/pdf" in cls.VARIANTS_ENABLED_FOR:
            if shutil.which("pdftoppm") is None:
                raise ImportError(
                    "preview_pdf requires the `pdftoppm` command from poppler. "
                    "Install poppler (https://poppler.freedesktop.org/) and ensure "
                    "`pdftoppm` is on PATH."
                ) from None

        if "video/*" in cls.VARIANTS_ENABLED_FOR:
            if shutil.which("ffmpeg") is None:
                raise ImportError(
                    "preview_video requires the `ffmpeg` command from ffmpeg v3.4+. "
                    "Install ffmpeg (https://ffmpeg.org/) and ensure `ffmpeg` is on PATH."
                ) from None

    @classmethod
    def _get_service(cls, service_name: str) -> Service:
        """Look up (and cache) a configured Service by name.

        To add your own service, subclass `proper.storage.Service`
        implementing the required methods. Then add a config with the
        class name as the type. For example:

        ```python
        STORAGES = {
            "gcs": {"type": "GoogleCloud", "arg1": "value1"},
        }
        STORAGE = "gcs"
        ```
        """
        if service_name in cls._services:
            return cls._services[service_name]

        config = dict(cls._app.config.get("STORAGES", {}).get(service_name, {}))
        service_type = config.pop("type", "")
        available = {c.__name__: c for c in Service.__subclasses__()}
        service_cls = available.get(service_type)
        if service_cls is None:
            raise ValueError(
                f"Unknown service type '{service_type}' for '{service_name}'. "
                f"Available types: {', '.join(available.keys())}"
            )
        service = service_cls(cls._app, **config)
        cls._services[service_name] = service
        return service


    # --- Purge-later helpers ---
    # These are wrapped as Huey tasks below (after the class body) so
    # registration happens in every process that imports this module -
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


def attachment_for(
    base_model_cls: t.Any,
    *,
    app: "App",
    default_service_name: str = "",
) -> type[_Attachment]:
    """Build an Attachment model class bound to `base_model_cls` (which carries
    the database) and `app` (which provides url_for / config / queue access).

    `base_model_cls` sits to the LEFT of `_Attachment` in the MRO so that:
    (a) peewee's metaclass inherits `_meta` (and therefore the database
        binding) from `base_model_cls`, and
    (b) save/select/etc. overrides on the consumer's base model (timestamps,
        audit hooks, ...) take precedence over `_Attachment`'s defaults.
        `_Attachment.save()` still runs via the normal `super()` chain, so
        consumer overrides must call `super().save(...)` as usual.
    """

    class Attachment(base_model_cls, _Attachment):
        _app = app
        _default_service_name = default_service_name
        # Fresh per-subclass dict for the service-instance cache.
        _services: t.ClassVar[dict[str, Service]] = {}

        id: str = pw.CharField(32, primary_key=True)  # type: ignore
        service_name: str = pw.CharField(64)  # type: ignore
        filename: str = pw.CharField(255, default="")  # type: ignore
        content_type: str = pw.CharField(64, default=DEFAULT_CONTENT_TYPE)  # type: ignore
        byte_size: int = pw.IntegerField(default=0)  # type: ignore
        created_at: "datetime" = pw.DateTimeField(default=pw.utcnow)  # type: ignore
        metadata: dict | None = JSONField(null=True)  # type: ignore
        parent: t.Self | None = pw.ForeignKeyField("self", null=True)  # type: ignore
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

    # Namespace task names by the base class so multiple Attachment classes
    # (e.g. distinct bases on the same app) don't collide in Huey's registry.
    # The name must be deterministic - web and worker derive the same string
    # from the same `base_model_cls`, so messages dispatched in one process
    # resolve in the other.
    task_ns = f"{base_model_cls.__module__}.{base_model_cls.__qualname__}"
    Attachment._purge_by_id = app.queue.task(name=f"{task_ns}._purge_by_id")(
        Attachment._purge_by_id
    )
    Attachment._purge_variants_by_id = app.queue.task(
        name=f"{task_ns}._purge_variants_by_id"
    )(Attachment._purge_variants_by_id)

    return Attachment
