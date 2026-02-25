import typing as t

import itsdangerous

from ..errors import BadSignature
from ..global_context import current
from ..units import YEAR
from .attachment import get_attachment_mixin
from .services import Service


if t.TYPE_CHECKING:
    from ..app import App
    from ..types import TAttachment, TUpload


class Storage:
    def __init__(self, app: "App") -> None:
        self.app = app
        self.signer = app.get_signer("proper.storage")
        self._services: dict[str, Service] = {}
        service_name = app.config.get("STORAGE", "")
        self.Attachment = get_attachment_mixin(self, service_name)

    def url_for(self, obj: "TAttachment") -> str:
        signed_pk = self.signer.sign(str(obj.id))
        if obj.public:
            return self.app.url_for("PublicAttachment.show", pk=obj.id)
        else:
            return self.app.url_for("Attachment.show", signed_pk=signed_pk)

    def get_public_attachment(self, pk: str) -> "TAttachment | None":
        return self.Attachment.get_or_none(
            self.Attachment.id == pk,
            self.Attachment.public == True,  # noqa: E712
        )

    def get_attachment(self, signed_pk: str, max_age: int = YEAR) -> "TAttachment | None":
        max_age = max(max_age, 0) or YEAR
        try:
            pk = self.signer.unsign(signed_pk, max_age=max_age).decode()  # type: ignore
            return self.Attachment.get_or_none(self.Attachment.id == pk)
        except itsdangerous.BadSignature as err:
            if self.app.debug:
                raise BadSignature from err
            return None

    def send_file(self, obj: "TAttachment"):
        as_attachment = not self._is_inline_content_type(obj.content_type)
        service = self.get_service(obj.service_name)
        return service.send_file(
            obj,
            response=current.response,
            as_attachment=as_attachment,
        )

    def upload(self, filesto: "TUpload", obj: "TAttachment"):
        service = self.get_service(obj.service_name)
        service.upload(filesto, obj)

    def get_service(self, service_name: str) -> Service:
        """To add your own service, subclass `proper.storage.Service`
        implementing the required methods. Then add a config with the
        class name as the type.

        For example, if you have a subclass of `Service` called "GoogleCloud",
        add a config like this:

        ```python
        STORAGE_SERVICES = {
            ...
            "gcs": {
                "type": "GoogleCloud"  # must match the class name
                "arg1": "value1"  # any other args you need
            }
        }

        STORAGE = "gcs"
        ```
        """
        if service_name in self._services:
            return self._services[service_name]

        config = dict(self.app.config.get("STORAGE_SERVICES", {}).get(service_name, {}))
        service_type = config.pop("type", "")
        available = {cls.__name__: cls for cls in Service.__subclasses__()}
        cls = available.get(service_type)
        if cls is None:
            raise ValueError(
                f"Unknown service type '{service_type}' for '{service_name}'. "
                f"Available types: {', '.join(available.keys())}"
            )
        service = cls(self.app, **config)
        self._services[service_name] = service
        return service

    def _is_inline_content_type(self, content_type: str) -> bool:
        allowed = self.app.config.get("STORAGE_ALLOWED_INLINE_CONTENT_TYPES", ())
        return any(content_type.startswith(ct) for ct in allowed)

    def purge(self, obj: "TAttachment", later: bool = False):
        if later:
            self._enqueue(self.purge, obj)
            return

        service = self.get_service(obj.service_name)
        service.purge(obj)
        self.purge_variants(obj)
        obj.delete_instance()

    def purge_variants(self, obj: "TAttachment", later: bool = False):
        if later:
            self._enqueue(self.purge_variants, obj)
            return

        for variant in obj.variants:
            service = self.get_service(variant.service_name)
            service.purge(variant)
            variant.delete_instance()

    def _enqueue(self, fn, *args, **kwargs):
        task = self.app.queue.task()(fn)
        task(*args, **kwargs)

    def download(self, obj: "TAttachment"):
        service = self.get_service(obj.service_name)
        return service.download(obj)
