import shutil
import tempfile
from pathlib import Path
from uuid import uuid4
from typing import TYPE_CHECKING

from .service import Service

if TYPE_CHECKING:
    from typing import Any, IO, Tuple, Union

    from multipart import MultipartPart
    from proper import App

    from ..file_data import FileData


class DiskService(Service):
    def __init__(self, app: "App", root: str, **kw) -> None:
        self.root = app.root_path.parent / root
        self.root.mkdir(parents=True, exist_ok=True)

    def upload(
        self, filesto: "Union[MultipartPart, IO]", fdata: "FileData"
    ) -> "FileData":
        key = str(uuid4().hex)
        if hasattr(filesto, "save_as"):
            byte_size = self._save_multipart_part(filesto, key)
        else:
            byte_size = self._save_regular_file(filesto, key)

        fdata.key = key
        fdata.byte_size = byte_size
        return fdata

    def download_to_tempfile(self, fdata: "FileData") -> str:
        tfolder = Path(tempfile.mkdtemp())
        tfile = tfolder / fdata.key
        shutil.copy2(src=self.root / fdata.key, dst=tfile)
        return str(tfile)

    def _save_multipart_part(self, filesto: "MultipartPart", key: str) -> int:
        return filesto.save_as(self.root / key)

    def _save_regular_file(self, file: "IO", key) -> int:
        path = self.root / key
        path.write_bytes(file.read())
        return path.stat().st_size
