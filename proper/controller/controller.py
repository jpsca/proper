"""A base controller class, all other application controllers must
inherit from. Stores data available to the view/template.
"""
from pathlib import Path
from typing import Any, Optional, Union

from ..app import App
from ..constants import HEAD
from ..helpers import MultiDict, jsonplus
from ..request_wrapper import Request
from ..response_wrapper import Response
from ..status import not_modified, ok, see_other
from .request_forgery_protection import RequestForgeryProtection


__all__ = ("Controller",)

TStringOrPath = Union[str, Path]


class Controller(RequestForgeryProtection):
    action_name: str

    def __before__(self) -> None:
        pass

    def __after__(self) -> None:
        pass

    def __init__(
        self,
        *,
        request: Optional[Request] = None,
        response: Optional[Response] = None,
        app: Optional[App] = None,
    ) -> None:
        self.request = request or Request()
        self.response = response or Response()
        self.app = app

    @property
    def params(self) -> MultiDict:
        params = MultiDict()
        params.update(self.request.query)
        params.update(self.request.form)
        params.update(self.request.matched_params or {})
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
            self.response.status_code = status

        if json is not None:
            self.response.content_type = "application/json"
            return jsonplus.dumps(json)

        if text is not None:
            self.response.content_type = "text/plain"
            return text

        # The template doesn't have a extension so you can choose to use
        # the default template name but changing the response format from the
        # default, for example, using ".json" instead of ".html".
        template = template or self.response.template
        filename = self.get_template_filename(template)
        return self.app.render(filename, **vars(self))

    def get_template_filename(self, template: str) -> str:
        """Override to use a different schema, for example, to
        not use the ".jinja" postfix."""
        return f"{template}{self.response.format}.jinja"

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
        return self.response.redirect_to(
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

        self._call_mro_method("__before__")
        if self.response.stop:
            return

        if not self.response.dispatched:
            self._call()

        self._call_mro_method("__after__")

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
        request, response = self.request, self.response
        method = getattr(self, self.action_name)
        ret_value = method()

        if response.is_fresh:
            response.status_code = not_modified
            response.body = ""
            return

        if response.stop or request.request_method == HEAD:
            return

        if ret_value is not None:
            response.body = ret_value

        if not response.has_body:
            response.body = self.render()
