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
    """A route for static files."""

    def __init__(
        self,
        path: str,
        name: str,
        *,
        root: str | Path,
        allowed_ext: t.Iterable[str] | None,
        host: str | None = None,
        defaults: dict | None = None,
    ) -> None:
        from proper.view import StaticFiles

        defaults = defaults or {}
        defaults["root"] = root
        if allowed_ext:
            defaults["allowed_ext"] = allowed_ext

        super().__init__(
            GET,
            path,
            to=StaticFiles.show,
            name=name,
            host=host,
            defaults=defaults,
        )

    def format(self, **kw) -> str:
        filename: str = kw.get("file", "")
        if not filename:
            return super().format(**kw)

        root = Path(self.defaults["root"])
        relpath = Path(filename.lstrip(os.path.sep))
        filepath = root / relpath
        if not filepath.is_file():
            return super().format(**kw)

        stat = filepath.stat()
        mtime = stat.st_mtime_ns or stat.st_mtime
        fingerprint = sha256(str(mtime).encode()).hexdigest()

        ext = "".join(relpath.suffixes)
        stem = relpath.name.removesuffix(ext)
        parent = relpath.parent
        kw["file"] = f"{parent}/{stem}-{fingerprint}{ext}"

        return super().format(**kw)


static = Static
