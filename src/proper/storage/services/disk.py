import os
import re
import typing as t
import unicodedata
from pathlib import Path

from proper.helpers import copy_file
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
        path.unlink(missing_ok=True)
        self._remove_empty_dirs(path.parent)

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

    def move_from_legacy_path(self, att: "_Attachment") -> bool:
        """Moves the file of `att` from where versions before 0.33 stored it
        to its current path. Returns whether it was moved.

        Run it once for every attachment of an app that stored files with
        an older version. The old paths only used the first four characters
        of the id, so two attachments with the same filename could share
        the same file. When that happened, only the last one written is
        there, and the first attachment to move it takes it.
        """
        legacy_path = self._get_legacy_path(att)
        path = self._get_path(att)
        if path.exists() or not legacy_path.is_file():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.rename(path)
        self._remove_empty_dirs(legacy_path.parent)
        return True

    def _get_path(self, att: "_Attachment") -> Path:
        # The full id is part of the path, so two attachments with the same
        # filename never share a file. The first two levels only spread the
        # folders, so no folder gets too many.
        key = str(att.id)
        filename = secure_filename(att.filename or key)
        return self.root / key[:2] / key[2:4] / key / filename

    def _get_legacy_path(self, att: "_Attachment") -> Path:
        key = str(att.id)
        filename = secure_filename(att.filename or key)
        return self.root / key[:2] / key[2:4] / filename

    def _remove_empty_dirs(self, path: Path) -> None:
        """Removes `path` and its parents, up to `self.root`, while empty."""
        while path != self.root and self.root in path.parents:
            if not path.is_dir() or not is_dir_empty(path):
                return
            path.rmdir()
            path = path.parent


def is_dir_empty(path):
    with os.scandir(path) as scan:
        return next(scan, None) is None



RX_FILENAME_ASCII_STRIP = re.compile(r"[^A-Za-z0-9_.-]")

WINDOWS_DEVICE_FILES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}


def secure_filename(filename: str) -> str:
    r"""Pass it a filename and it will return a secure version of it.

    This filename can then safely be stored on a regular file system and
    passed to `os.path.join`. The filename returned is an ASCII only
    string for maximum portability.

    On windows systems the function also makes sure that the file is not
    named after one of the special device files.

    >>> secure_filename("My cool movie.mov")
    'My_cool_movie.mov'
    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'
    >>> secure_filename('i contain cool \xfcml\xe4uts.txt')
    'i_contain_cool_umlauts.txt'

    The function might return an empty filename. It's your responsibility
    to ensure that the filename is unique and that you abort or
    generate a random filename if the function returned an empty one.

    Arguments:

    - filename: the filename to secure

    """
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    for sep in os.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, " ")

    filename = "_".join(filename.split())
    filename = str(RX_FILENAME_ASCII_STRIP.sub("", filename)).strip("._")

    # on nt a couple of special files are present in each folder. We
    # have to ensure that the target file is not such a filename. In
    # this case we prepend an underline
    if (
        os.name == "nt"
        and filename
        and filename.split(".")[0].upper() in WINDOWS_DEVICE_FILES
    ):
        filename = f"_{filename}"

    return filename
