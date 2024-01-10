"""A base controller class, all other application controllers must
inherit from. Stores data available to the component.
"""
import typing as t
from inspect import isclass

from .app import App
from .constants import HEAD
from .helpers import MultiDict, jsonplus
from .request import Request
from .response import Response
from .status import not_modified


__all__ = ("Controller",)


class Controller:
    middleware: t.Sequence[t.Any]

    def __init__(
        self,
        app: App,
        request: Request,
        response: Response,
    ) -> None:
        self.app = app
        self.request = request
        self.response = response
        self.middleware = [
            m() if isclass(m) else m
            for m in getattr(self, "middleware", [])
        ]

    @property
    def params(self) -> MultiDict:
        params = MultiDict()
        params.update(self.request.query)
        params.update(self.request.form)
        params.update(self.request.matched_params or {})
        return params

    def render(
        self,
        name: str,
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
        return self.app.catalog.render(
            name,
            **vars(self)
        )

    # Private

    def _dispatch(self, action_name: str) -> Response | None:
        for m in self.middleware:
            early_response = m.before(self)
            if early_response is not None:
                return early_response

        self._call(action_name)

        for m in self.middleware:
            early_response = m.after(self)
            if early_response is not None:
                return early_response

    def _call(self, action_name: str) -> None:
        # We call the endpoint but we do not expect a result value.
        # All the side effects of this call should be stored in the same
        # controller and in `resp`.
        method = getattr(self, action_name)
        ret_value = method()

        if self.response.is_fresh(request=self.request):
            self.response.status = not_modified
            self.response.body = ""
            return

        if self.request.request_method == HEAD:
            return

        if ret_value is not None:
            self.response.body = ret_value
