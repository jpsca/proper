"""A base controller class, all other application controllers must
inherit from. Stores data available to view/template.
"""
from typing import Any, Dict, Optional

from proper.app import App
from proper.request import Request
from proper.response import Response
from proper.status import not_modified


__all__ = ("BaseController",)


class BaseController:
    def before_action(self, action: str) -> None:
        pass

    def after_action(self, action: str) -> None:
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
        self._app = app

    def _dispatch(self, action: str) -> None:
        self.before_action(action)
        if self.resp.stop:
            return

        if not self.resp.dispatched:
            self._call(action)

        self.after_action(action)

    def _call(self, action: str) -> None:
        # We call the endpoint but we do not expect a result value.
        # All the side effects of this call should be stored in the same
        # controller and in `resp`.
        req, resp = self.req, self.resp
        method = getattr(self, action)
        method(**req.matched_params)

        if resp.is_fresh:
            resp.status_code = not_modified
            resp.body = ""
            return

        if req.real_method == "HEAD" or resp.has_body or resp.stop:
            return

        resp.body = self._render()

    def _render(self) -> str:
        # The template doesn't have a extension so the action can choose to use
        # the default template name but changing the response format from the
        # default, for example, using ".json" instead of ".html".
        template = f"{self.resp.template}{self.resp.format}.jinja"
        return self._app.render(template, **self._as_dict())

    def _as_dict(self) -> Dict[str, Any]:
        return {
            name: getattr(self, name) for name in dir(self) if not name.startswith("_")
        }
