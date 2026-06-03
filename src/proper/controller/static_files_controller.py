import os
import re
import typing as t
from pathlib import Path

from ..errors import NotFound
from ..status import not_modified
from .controller import Controller


if t.TYPE_CHECKING:
    from ..types import Iterable


RX_FINGERPRINT = re.compile("(.*)-([a-f0-9]{64})")


class StaticFilesController(Controller):
    def show(self):
        root: Path = Path(self.defaults["root"])
        public: bool = self.defaults["public"]
        file: str = self.params.get("file", "")
        relpath = Path(file.lstrip(os.path.sep))
        ext = "".join(relpath.suffixes)

        allowed_ext: Iterable[str] | None = self.defaults.get("allowed_ext")
        if allowed_ext:
            if ext not in allowed_ext:
                raise NotFound("File does not exist")

        # Ignore the fingerprint in the filename
        # since is only for managing the cache in the client
        stem = relpath.name.removesuffix(ext)
        fingerprinted = RX_FINGERPRINT.match(stem)
        if fingerprinted:
            stem = fingerprinted.group(1)
            relpath = relpath.with_name(f"{stem}{ext}")

        filepath: Path = (root / relpath).resolve()

        if not filepath.is_relative_to(root.resolve()):
            raise NotFound(f"File `{file}` does not exist")

        if not filepath.is_file():
            raise NotFound(f"File `{file}` does not exist")

        mtime = filepath.stat().st_mtime
        self.response.last_modified = mtime

        last_modified = self.response.last_modified
        if_modified_since = self.request.if_modified_since
        if last_modified and if_modified_since and last_modified <= if_modified_since:
            self.response.status = not_modified
        else:
            x_sendfile = self.app.config.get("STATIC_X_SENDFILE_HEADER", "")
            self.response.send_file(
                filepath,
                as_attachment=False,
                x_sendfile_header=x_sendfile,
            )

        if fingerprinted:
            self.response.set_cache_control(
                "max-age=31536000",
                "public" if public else "private",
                "immutable",
            )
        else:
            self.response.set_cache_control(
                "max-age=0",
                "public" if public else "private",
                "must-revalidate",
            )

        # Ensures that things still work as expected when
        # your files are served from a CDN, rather than
        # your primary domain.
        self.response.headers.set("Access-Control-Allow-Origin", "*")
