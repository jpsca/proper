import typing as t

import itsdangerous

from proper.errors import BadSignature

from .attachment import get_attachment_class
from .services import Service


if t.TYPE_CHECKING:
    from proper.core import App
    from proper.helpers import DotDict

    from .types import TAttachment, TUpload


ONE_YEAR = 32_000_000  # 60 * 60 * 24 * 365 (aprox 1 year)


class Storage:
    def __init__(self, app: "App", config: "DotDict") -> None:
        self.app = app
        self.config = config
        self.signer = app.get_timestamp_signer("proper.storage")
        self.Attachment = get_attachment_class(self, config)

    def url_for(self, obj: "TAttachment") -> str:
        signed_pk = self.signer.sign(obj.key)
        return self.app.url_for(
            "Storage.show",
            signed_pk=signed_pk,
            filename=obj.filename
        )

    def get_attachment(self, signed_pk: str, max_age: int = ONE_YEAR) -> str | None:
        max_age = max(max_age, 0) or ONE_YEAR
        try:
            pk = self.signer.unsign(signed_pk, max_age=max_age).decode()  # type: ignore
            return self.Attachment.get_or_none(pk)
        except itsdangerous.BadSignature as err:
            if self.config.DEBUG:
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

        For example, if you have a service called "DigitalOcean", add a
        config like this:

        ```python
        STORAGE_SERVICES = {
            ...
            "do": {
                "type": "DigitalOcean"  # must match the class name
                "arg1": "value1"  # any other args you need
            }
        }

        STORAGE = "do"
        ```
        """
        config = self.config.STORAGE_SERVICES[self.config.STORAGE]
        services = {cls.__name__: cls for cls in Service.__subclasses__()}
        cls = services.get(service_name)
        if cls is None:
            raise ValueError(
                f"Unknown service: {service_name}. "
                f"Must be one of: {', '.join(services.keys())}"
            )
        return cls(self.app, config)

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
