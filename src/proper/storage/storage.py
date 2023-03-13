import typing as t

from .attachment import get_attachment_class
from .services import Service

if t.TYPE_CHECKING:
    from ..app import App
    from ..helpers import DotDict
    from .types import TAttachment, TUpload


class Storage:
    def __init__(self, app: "App", config: "DotDict") -> None:
        self.app = app
        self.config = config
        self.signer = app.get_signer("proper.storage")
        self.Attachment = get_attachment_class(self, config)

    def url_for(self, obj: "TAttachment") -> str:
        signed_pk = self.signer.sign(obj.key)
        return self.app.url_for(
            "Storage.show",
            signed_pk=signed_pk,
            filename=obj.filename
        )

    def get_key(self, signed_pk: str) -> str | None:
        if not self.signer.validate(signed_pk):
            return None
        return self.signer.unsign(signed_pk)

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
        do = DotDict()
        do.type = "DigitalOcean"  # must match the class name
        do.arg1 = "value1"  # any other args you need
        storage_config.do = do

        ...

        storage_config.service = "do"
        ```
        """
        config = self.config[service_name]
        services = {cls.__name__: cls for cls in Service.__subclasses__()}
        cls = services.get(service_name)
        if cls is None:
            raise ValueError(
                f"Unknown service: {service_name}. "
                f"Must be one of: {', '.join(services.keys())}"
            )
        return cls(self.app, config)

    def show(self, obj: "TAttachment"):
        pass

    def purge(self, obj: "TAttachment", later: bool = False):
        pass

    def purge_variants(self, obj: "TAttachment", later: bool = False):
        pass

    def download(self, obj: "TAttachment"):
        service = self.get_service(obj.service_name)
        return service.download(obj)
