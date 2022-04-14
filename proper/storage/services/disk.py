from uuid import uuid4
from typing import TYPE_CHECKING

from .base import BaseService

if TYPE_CHECKING:
    from typing import IO, Union
    from multipart import MultipartPart
    from proper import App
    from ..blob import Blob


class DiskService(BaseService):
    def __init__(self, app: "App", root: str, **kwargs) -> None:
        self.root = app.root_path.parent / root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, filesto: "Union[MultipartPart, IO]", blob: "Blob") -> "Blob":
        blob.key = str(uuid4().hex)
        if hasattr(filesto, "save_as"):
            self.save_multipart_part(filesto, blob)
        else:
            self.save_regular_file(filesto, blob)
        return blob

    def save_multipart_part(self, filesto: "MultipartPart", blob: "Blob") -> None:
        blob.byte_size = filesto.save_as(self.root / blob.key)

    def save_regular_file(self, file: "IO", blob: "Blob") -> None:
        blob.byte_size = (self.root / blob.key).write_bytes(file.read())
