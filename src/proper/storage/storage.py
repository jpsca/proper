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
        self.Attachment = get_attachment_class(self, config)

    def url_for(self, obj: "TAttachment") -> str:
        return f"/storage/{obj.key}/{obj.filename}"

    def upload(self, filesto: "TUpload", obj: "TAttachment"):
        service = self.get_service(obj.service_name)
        service.upload(filesto, obj)

    def get_service(self, service_name: str) -> services.Service:
        config = self.config[service_name]
        config_name = config.service.capitalize()
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
        return service.download_to_tempfile(obj)
