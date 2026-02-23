import os
import typing as t
from pathlib import Path

from proper.request.multipart import copy_file
from .service import Service


if t.TYPE_CHECKING:
    from proper.app import App
    from proper.types import TAttachment, TUpload


class Disk(Service):
    def __init__(self, app: "App", **config: t.Any) -> None:
        self.root = app.root_path.parent / config["root"]
        self.root.mkdir(parents=True, exist_ok=True)
        super().__init__(app, **config)

    def upload(self, filesto: "TUpload", obj: "TAttachment") -> None:
        file: t.BinaryIO = getattr(filesto, "file", filesto)  # type: ignore

        path = self._get_path(obj)
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def send_file(self, obj: "TAttachment", response, as_attachment: bool = False) -> None:
        path = self._get_path(obj)
        response.send_file(
            path,
            mimetype=obj.content_type,
            as_attachment=as_attachment,
            download_name=obj.filename,
        )

    def purge(self, obj: "TAttachment") -> None:
        path = self._get_path(obj)
        parent = path.parent
        path.unlink(missing_ok=True)
        if parent.is_dir() and is_dir_empty(parent):
            parent.rmdir()

    def _get_path(self, obj: "TAttachment") -> Path:
        key = str(obj.id)
        filename = obj.filename or key
        return self.root / key[:2] / key[2:4] / filename


def is_dir_empty(path):
    with os.scandir(path) as scan:
        return next(scan, None) is None
