"""A base controller class, all other application controllers must
inherit from. Stores data available to the view/template.
"""
from pathlib import Path
from typing import Any, Optional, Union

from ..app import App
from ..helpers import MultiDict, jsonplus
from ..request import Request
from ..response import Response
from ..status import not_modified, ok, see_other
from .request_forgery_protection import RequestForgeryProtection


__all__ = ("Controller",)

TStringOrPath = Union[str, Path]


class Controller(RequestForgeryProtection):
    action_name: str

    def before_action(self) -> None:
        self.protect_from_forgery(self.action_name)

    def after_action(self) -> None:
        pass

    def __init__(
        self,
        *,
        req: Optional[Request] = None,
        resp: Optional[Response] = None,
        app: Optional[App] = None,
    ) -> None:
        self.req = req or Request()
        self.resp = resp or Response()
        self.app = app

    @property
    def params(self) -> MultiDict:
        params = MultiDict()
        params.update(self.req.query)
        params.update(self.req.form)
        params.update(self.req.matched_params or {})
        return params

    def render(
        self,
        template: Optional[str] = None,
        *,
        status: Optional[str] = None,
        json: Optional[Any] = None,
        text: Optional[Any] = None,
    ) -> str:
        if status is not None:
            self.resp.status_code = status

        if json is not None:
            self.resp.content_type = "application/json"
            return jsonplus.dumps(json)

        if text is not None:
            self.resp.content_type = "text/plain"
            return text

        # The template doesn't have a extension so you can choose to use
        # the default template name but changing the response format from the
        # default, for example, using ".json" instead of ".html".
        template = template or self.resp.template
        filename = self.get_template_filename(template)
        return self.app.render(filename, **vars(self))

    def get_template_filename(self, template: str) -> str:
        """Override to use a different schema, for example, to
        not use the ".jinja" postfix."""
        return f"{template}{self.resp.format}.jinja"

    def redirect_to(
        self,
        url_or_route: str,
        object: Optional[Any] = None,
        *,
        flash: Optional[str] = None,
        flash_type: str = "notice",
        status_code: str = see_other,
        **kwargs,
    ) -> None:
        return self.resp.redirect_to(
            url_or_route,
            object=object,
            flash=flash,
            flash_type=flash_type,
            status_code=status_code,
            **kwargs,
        )

    def send_data(
        self,
        data: bytes,
        *,
        disposition: str = "attachment",
        status: str = ok,
        type: str = "application/octet-stream",
    ):
        ...

    def send_file(
        self,
        path: TStringOrPath,
        *,
        disposition: str = "attachment",
        filename: Optional[str] = None,
        stream: bool = False,
        buffer_size: int = 1024,
        status: str = ok,
        type: str = "application/octet-stream",
    ):
        ...

    # Private

    def _dispatch(self, action_name: str) -> None:
        self.action_name = action_name

        self._call_mro_method("before_action")
        if self.resp.stop:
            return

        if not self.resp.dispatched:
            self._call()

        self._call_mro_method("after_action")

    def _call_mro_method(self, method_name: str) -> None:
        visited = []
        # last item is "object"
        mro = self.__class__.mro()[:-1]

        for cls in mro:
            method = getattr(cls, method_name, None)
            if method and method not in visited:
                method(self)
                visited.append(method)

    def _call(self) -> None:
        # We call the endpoint but we do not expect a result value.
        # All the side effects of this call should be stored in the same
        # controller and in `resp`.
        req, resp = self.req, self.resp
        method = getattr(self, self.action_name)
        ret_value = method()

        if resp.is_fresh:
            resp.status_code = not_modified
            resp.body = ""
            return

        if resp.stop or req.request_method == "HEAD":
            return

        if ret_value is not None:
            resp.body = ret_value

        if not resp.has_body:
            resp.body = self.render()
