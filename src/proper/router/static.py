import os
import typing as t
from hashlib import sha256
from pathlib import Path

from .route import GET, Route


__all__ = (
    "Static",
    "static",
)


class Static(Route):
    """A route for static files.

    Arguments:

    - url:
        The base URL for these static files.

    - root:
        The absolute path to the folder where the static files are.

    - name:
        This name can be any unique string eg: "static", "files", "assets", etc.

    - allowed_ext:
        Optional. If included, only the files with extensions on this list
        wil be returned. Include `""` for files without any extension.

    - public [True]:
        By default the Cache-Control header of static files is public, set this to
        `False` if you want the files to *not* be cacheable by other devices
        (like proxy caches).

    - fingerprint [True]:
        If True, adds, insert a hash of the updated time after the name of the file,
        but before the extension. This strategy encourages long-term caching while
        ensuring that new copies are only requested when the content changes, as
        any modification alters the fingerprint and thus the filename.

    - host:
        Optional. Host for this route, including any subdomain
        and an optional port. Examples: "www.example.com", "localhost:5000".

    - defaults:
        Optional. A dict with extra values that will be sent to the view.

    """

    def __init__(
        self,
        url: str,
        *,
        root: str | Path,
        name: str = "",
        allowed_ext: t.Iterable[str] | None = (),
        public: bool = True,
        fingerprint: bool = True,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> None:
        from proper.view import StaticFiles

        defaults = defaults or {}
        defaults["root"] = root
        defaults["public"] = bool(public)
        defaults["fp"] = bool(fingerprint)
        if allowed_ext:
            defaults["allowed_ext"] = allowed_ext
        path = url.strip("/") + "/:file<path>"

        super().__init__(
            GET,
            path,
            to=StaticFiles.show,
            name=name,
            host=host,
            defaults=defaults,
        )

    def format(self, **kw) -> str:
        if not self.defaults["fp"]:
            return super().format(**kw)

        root = Path(self.defaults["root"])
        filename: str = kw["file"]
        relpath = Path(filename.lstrip(os.path.sep))
        filepath = root / relpath
        if not filepath.is_file():
            return super().format(**kw)

        stat = filepath.stat()
        fingerprint = sha256(str(stat.st_mtime).encode()).hexdigest()

        ext = "".join(relpath.suffixes)
        stem = relpath.name.removesuffix(ext)
        parent = str(relpath.parent)
        parent = "" if parent == "." else f"{parent}/"

        kw["file"] = f"{parent}{stem}-{fingerprint}{ext}"

        return super().format(**kw)


static = Static
