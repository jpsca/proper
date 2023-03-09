import typing as t


from .attachment import get_attachment_class
from . import services

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

    def get_service(self, service_name: str) -> services.Service:
        config = self.config[service_name]
        config_name = config.type.capitalize()
        class_name = f"{config_name}Service"
        Service = getattr(services, class_name)
        return Service(self.app, config)

    def show(self, obj: "TAttachment"):
        pass

    def purge(self, obj: "TAttachment", later: bool = False):
        pass

    def purge_variants(self, obj: "TAttachment", later: bool = False):
        pass

    def download(self, obj: "TAttachment"):
        service = self.get_service(obj.service_name)
        return service.download(obj)
