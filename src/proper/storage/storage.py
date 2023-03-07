import mimetypes
import typing as t

from .attachment import get_attachment_class
from . import services

if t.TYPE_CHECKING:
    from ..app import App
    from ..helpers import DotDict
    from .types import TAttachment, TUpload


DEFAULT_CONTENT_TYPE = "application/octet-stream"


class Storage:
    def __init__(self, app: "App", config: "DotDict") -> None:
        self.app = app
        self.config = config
        self.Attachment = get_attachment_class(self)

    def upload(self,
        filesto: "TUpload",
        obj: "TAttachment",
        service_name: str | None = None,
    ):
        filename = obj.filename or getattr(filesto, "filename", "")
        content_type = obj.content_type or getattr(filesto, "content_type", "") or ""
        if filename and not content_type:
            guess = mimetypes.guess_type(filename, strict=False)
            content_type = guess[0] or ""
        content_type = content_type or DEFAULT_CONTENT_TYPE
        byte_size = obj.byte_size or 0

        service_name = service_name or self.config.service or ""
        service = self.get_service(service_name)
        service.upload(
            obj,
            filesto,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
        )

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
        pass
