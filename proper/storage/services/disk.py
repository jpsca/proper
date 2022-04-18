import shutil
import tempfile
from pathlib import Path
from uuid import uuid4
from typing import TYPE_CHECKING

from .service import Service

if TYPE_CHECKING:
    from typing import Any, IO, Union
    from multipart import MultipartPart
    from proper import App
    from ..blob import Blob


class DiskService(Service):
    def __init__(self, app: "App", root: str, **kw) -> None:
        self.root = app.root_path.parent / root
        self.root.mkdir(parents=True, exist_ok=True)

    def upload(self, filesto: "Union[MultipartPart, IO]", blob: "Any") -> "Any":
        blob.key = str(uuid4().hex)
        if hasattr(filesto, "save_as"):
            self._save_multipart_part(filesto, blob)
        else:
            self._save_regular_file(filesto, blob)
        return blob

    def download_blob_to_tempfile(self, blob: "Blob") -> str:
        tfolder = Path(tempfile.mkdtemp())
        tfile = tfolder / blob.key
        shutil.copy2(src=self.root / blob.key, dst=tfile)
        return str(tfile)

    def _save_multipart_part(self, filesto: "MultipartPart", blob: "Any") -> None:
        blob.byte_size = filesto.save_as(self.root / blob.key)

    def _save_regular_file(self, file: "IO", blob: "Any") -> None:
        blob.byte_size = (self.root / blob.key).write_bytes(file.read())
