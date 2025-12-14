"""A base controller class, all other application controllers
must inherit from. Stores data available to the views.
"""
import os
import re
import typing as t
from pathlib import Path

from .errors import NotFound
from .helpers import MultiDict, jsonplus
from .status import not_modified


if t.TYPE_CHECKING:
    from .core.app import App
    from .request import Request
    from .response import Response
    from .types import TIterable


__all__ = ("Controller",)

class Controller:
    etag = ""

    def __init__(
        self,
        app: "App",
        request: "Request",
        response: "Response",
    ) -> None:
        self.app = app
        self.request = request
        self.response = response

    @property
    def params(self) -> MultiDict:
        params = MultiDict()
        params.update(self.request.query)
        params.update(self.request.form)
        params.update(self.request.matched_params or {})
        return params

    @property
    def defaults(self) -> dict:
        defaults = {}
        if self.request.matched_route:
            defaults = self.request.matched_route.defaults
        return defaults

    def render(
        self,
        name: str = "",
        *,
        status: str | None = None,
        json: t.Any = None,
        text: t.Any = None,
    ) -> str:
        if status is not None:
            self.response.status = status

        if json is not None:
            self.response.mimetype = "application/json"
            return jsonplus.dumps(json)

        if text is not None:
            self.response.mimetype = "text/plain"
            return text

        assert self.app.catalog
        return self.app.catalog.render(name, **vars(self))

    # Private

    def _dispatch(self, action_name: str) -> "Response | None":
        mro = type(self).mro()

        for cls in mro:
            before = cls.__dict__.get("before", None)
            if before:
                before(self)
                if self.response.has_body:
                    return

        self._call(action_name)

        for cls in mro[::-1]:
            after = cls.__dict__.get("after", None)
            if after:
                after(self)

    def _call(self, action_name: str) -> None:
        # All the side effects of this call should be stored in the same
        # view and in `resp`.
        method = getattr(self, action_name)
        ret_value = method()

        if self.response.is_fresh(request=self.request):
            self.response.status = not_modified
            self.response.body = ""
            return

        if ret_value is not None:
            self.response.body = ret_value
            return

        if not self.response.has_body:
            cmod = self.__class__.__module__.split(".", 2)[-1]
            cmod = cmod.removesuffix("_controller")
            cmod = cmod.replace(".", "/")
            infered_view = f"pages/{cmod}/{action_name}.jinja"
            self.response.body = self.render(infered_view)
            return


RX_FINGERPRINT = re.compile("(.*)-([abcdef0-9]{64})")


class StaticFilesController(Controller):
    def show(self):
        root: Path = Path(self.defaults["root"])
        public: bool = self.defaults["public"]
        file: str = self.params.get("file", "")
        relpath = Path(file.lstrip(os.path.sep))
        ext = "".join(relpath.suffixes)

        allowed_ext: TIterable[str] | None = self.defaults.get("allowed_ext")
        if allowed_ext:
            if ext not in allowed_ext:
                raise NotFound("File does not exists")

        # Ignore the fingerprint in the filename
        # since is only for managing the cache in the client
        stem = relpath.name.removesuffix(ext)
        fingerprinted = RX_FINGERPRINT.match(stem)
        if fingerprinted:
            stem = fingerprinted.group(1)
            relpath = relpath.with_name(f"{stem}{ext}")

        filepath: Path = (root / relpath).resolve()

        if not filepath.is_file():
            raise NotFound(f"File `{file}` does not exists")

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
