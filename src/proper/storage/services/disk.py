import os
import typing as t
from pathlib import Path

from proper.helpers import copy_file
from proper.helpers.imports import secure_filename
from .service import Service


if t.TYPE_CHECKING:
    from proper.app import App
    from proper.storage import _Attachment
    from proper.types import TUpload


class Disk(Service):
    def __init__(self, app: "App", **config: t.Any) -> None:
        self.app = app
        self.root = app.root_path.parent / config["root"]
        self.root.mkdir(parents=True, exist_ok=True)
        super().__init__(app, **config)

    def upload(self, upload: "TUpload", att: "_Attachment") -> None:
        file: t.BinaryIO = getattr(upload, "file", upload)  # type: ignore

        path = self._get_path(att)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fp:
            pos = file.tell()
            try:
                file.seek(0)
                att.byte_size = copy_file(file, fp)
            finally:
                file.seek(pos)

    def download(self, att: "_Attachment") -> bytes:
        path = self._get_path(att)
        return path.read_bytes()

    def send_file(self, att: "_Attachment", response, as_attachment: bool = False) -> None:
        path = self._get_path(att)
        response.send_file(
            path,
            mimetype=att.content_type,
            as_attachment=as_attachment,
            download_name=att.filename,
        )

    def purge(self, att: "_Attachment") -> None:
        path = self._get_path(att)
        parent_l1 = path.parent
        parent_l2 = parent_l1.parent

        path.unlink(missing_ok=True)
        if parent_l1.is_dir() and is_dir_empty(parent_l1):
            parent_l1.rmdir()
        if parent_l2.is_dir() and is_dir_empty(parent_l2):
            parent_l2.rmdir()

    def direct_upload_url(
        self, att: "_Attachment", *, checksum: str = ""
    ) -> "dict[str, t.Any]":
        """For Disk, there's nothing remote to PUT to — return our own
        bytes-receiving endpoint. The token in the URL authorizes that
        specific blob; the `upload` salt scopes it so a leaked download
        URL can't be repurposed to overwrite content. The resolver pairs
        it with a short TTL (see `DirectUploadController.update`) so a
        leaked upload URL only lives long enough for the browser PUT.
        """
        token = att.generate_token(salt="upload")
        url = self.app.url_for("DirectUpload.update", token=token, _full=True)
        headers = {"Content-Type": att.content_type or "application/octet-stream"}
        if checksum:
            headers["Content-MD5"] = checksum
        return {"url": url, "headers": headers}

    def _get_path(self, att: "_Attachment") -> Path:
        key = str(att.id)
        filename = secure_filename(att.filename or key)
        return self.root / key[:2] / key[2:4] / filename


def is_dir_empty(path):
    with os.scandir(path) as scan:
        return next(scan, None) is None
