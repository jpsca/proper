import typing as t
from pathlib import Path

from proper.request.multipart import copy_file

from .service import Service


if t.TYPE_CHECKING:
    from proper.core import App
    from proper.helpers import DotDict

    from ..types import TAttachment, TUpload


class Disk(Service):
    def __init__(self, app: "App", config: "DotDict") -> None:
        self.root = app.root_path.parent / config.root
        self.root.mkdir(parents=True, exist_ok=True)
        super().__init__(app, config)

    def upload(self, filesto: "TUpload", obj: "TAttachment") -> None:
        file: t.BinaryIO = getattr(filesto, "file", filesto)  # type: ignore

        path = self._get_path(obj)
        with open(path, "wb") as fp:
            pos = file.tell()
            try:
                file.seek(0)
                obj.byte_size = copy_file(file, fp)
            finally:
                file.seek(pos)

    def download(self, obj: "TAttachment") -> bytes:
        path = self._get_path(obj)
        return path.read_bytes()

    def send_file(self, obj: "TAttachment") -> bytes:
        raise NotImplementedError

    def purge(self, obj: "TAttachment") -> None:
        raise NotImplementedError

    def _get_path(self, obj: "TAttachment") -> Path:
        filename = obj.filename or obj.key
        return self.root / obj.key[:2] / obj.key[2:4] / filename
