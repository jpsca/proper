from uuid import uuid4
from typing import TYPE_CHECKING

from ..blob import Blob
from .base import BaseService

if TYPE_CHECKING:
    from multipart import MultipartPart
    from proper import App


class DiskService(BaseService):
    def __init__(self, app: "App", root: str, **kwargs):
        self.root = app.root_path.parent / root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, filesto: "MultipartPart", blob: Blob) -> None:
        blob.key = str(uuid4().hex)
        blob.byte_size = filesto.save_as(self.root / blob.key)
        return blob
