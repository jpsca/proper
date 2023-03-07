import shutil
import tempfile
import typing as t
from pathlib import Path
from uuid import uuid4

from .service import Service

if t.TYPE_CHECKING:
    from ...app import App
    from ...helpers import DotDict
    from ..types import TAttachment, TUpload


class DiskService(Service):
    def __init__(self, app: "App", config: DotDict) -> None:
        self.root = app.root_path.parent / config.root
        self.root.mkdir(parents=True, exist_ok=True)
        super().__init__(config)

    def upload(
        self,
        obj: "TAttachment",
        filesto: "TUpload",
        filename: str,
        content_type: str,
        byte_size: int,
    ) -> None:
        key = str(uuid4().hex)
        if hasattr(filesto, "save_as"):
            byte_size = self._save_multipart_part(filesto, key)
        else:
            byte_size = self._save_regular_file(filesto, key)

        obj.key = key
        obj.byte_size = byte_size

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
