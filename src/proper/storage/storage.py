import typing as t

import itsdangerous

from proper.errors import BadSignature

from .attachment import get_attachment_mixin
from .services import Service


if t.TYPE_CHECKING:
    from proper.core.app import App
    from proper.types import TAttachment, TUpload


ONE_YEAR = 32_000_000  # 60 * 60 * 24 * 365 (aprox 1 year)


class Storage:
    def __init__(self, app: "App") -> None:
        self.app = app
        self.signer = app.get_signer("proper.storage")
        service_name = app.config.get("STORAGE", "")
        self.Attachment = get_attachment_mixin(self, service_name)

    def url_for(self, obj: "TAttachment") -> str:
        signed_pk = self.signer.sign(obj.id)
        if obj.public:
            return self.app.url_for("PublicStorage.show", pk=obj.id)
        else:
            return self.app.url_for("Storage.show", signed_pk=signed_pk)

    def get_public_attachment(self, pk: str) -> "TAttachment | None":
        return self.Attachment.get(pk=pk, public=True)

    def get_attachment(self, signed_pk: str, max_age: int = ONE_YEAR) -> "TAttachment | None":
        max_age = max(max_age, 0) or ONE_YEAR
        try:
            pk = self.signer.unsign(signed_pk, max_age=max_age).decode()  # type: ignore
            return self.Attachment.get_or_none(pk)
        except itsdangerous.BadSignature as err:
            if self.app.debug:
                raise BadSignature from err
            return None

    def send_file(self, obj: "TAttachment"):
        service = self.get_service(obj.service_name)
        return service.send_file(obj)

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
        services = {cls.__name__: cls for cls in Service.__subclasses__()}
        cls = services.get(service_name)
        if cls is None:
            raise ValueError(
                f"Unknown service: {service_name}. "
                f"Must be one of: {', '.join(services.keys())}"
            )
        config = self.app.config.get("STORAGE_SERVICES", {}).get(service_name, {})
        return cls(self.app, **config)

    def show(self, obj: "TAttachment"):
        # TODO
        raise NotImplementedError

    def purge(self, obj: "TAttachment", later: bool = False):
        if later:
            # TODO
            raise NotImplementedError
            return
        service = self.get_service(obj.service_name)
        service.purge(obj)
        self.purge_variants(obj)
        obj.delete_instance()

    def purge_variants(self, obj: "TAttachment", later: bool = False):
        if later:
            # TODO
            raise NotImplementedError
            return
        # TODO
        raise NotImplementedError

    def download(self, obj: "TAttachment"):
        service = self.get_service(obj.service_name)
        return service.download(obj)
