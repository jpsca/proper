"""A base controller class, all other application controllers must
inherit from. Stores data available to the component.
"""
import typing as t

import inflection

from ..app import App
from ..constants import HEAD
from ..helpers import MultiDict, jsonplus
from ..request import Request
from ..response import Response
from ..status import not_modified
from .request_forgery_protection import RequestForgeryProtection


__all__ = ("Controller",)


class Controller(RequestForgeryProtection):
    def __before__(self) -> None:
        pass

    def __after__(self) -> None:
        pass

    def __init__(
        self,
        *,
        request: Request | None = None,
        response: Response | None = None,
        app: App | None = None,
    ) -> None:
        self.request = request or Request()
        self.response = response or Response()
        self.app = app
        self.redirect_to = self.response.redirect_to
        self.action_name = ""

    @property
    def params(self) -> MultiDict:
        params = MultiDict()
        params.update(self.request.query)
        params.update(self.request.form)
        params.update(self.request.matched_params or {})
        return params

    def render(
        self,
        component: str | None = None,
        *,
        status: str | None = None,
        json: t.Any = None,
        text: t.Any = None,
    ) -> str:
        if status is not None:
            self.response._status = status

        if json is not None:
            self.response.content_type = "application/json"
            return jsonplus.dumps(json)

        if text is not None:
            self.response.content_type = "text/plain; charset=utf-8"
            return text

        component = component or self.response.component
        assert component
        assert self.app and self.app.catalog

        return self.app.catalog.render(
            component,
            **vars(self)
        )

    # Private

    def _dispatch(self, action_name: str) -> None:
        self.action_name = action_name

        # Even if we might not use it, let set the inferred component name now
        # (unless is already set), so the action can overwrite it if they want.
        if not self.response.component:
            self.response.component = self._get_component_name()

        self._call_mro_method("__before__")
        if self.response.stop:
            return

        if not self.response.dispatched:
            self._call()

        self._call_mro_method("__after__")

    def _get_component_name(self):
        return f"{self.__class__.__name__}.{inflection.camelize(self.action_name)}"

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
            response._status = not_modified
            response.body = ""
            return

        if response.stop or request.request_method == HEAD:
            return

        if ret_value is not None:
            response.body = ret_value

        if not response.has_body:
            response.body = self.render()
