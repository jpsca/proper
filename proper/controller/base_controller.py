"""A base controller class, all other application controllers must
inherit from. Stores data available to view/template.
"""
from typing import Any, Dict, Optional

from ..app import App
from ..request import Request
from ..response import Response
from ..status import not_modified
from .request_forgery_protection import RequestForgeryProtection


__all__ = ("BaseController",)


class BaseController(RequestForgeryProtection):
    def before_action(self, action: str, params: Dict[str, Any]) -> None:
        self.protect_from_forgery(action)

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
        self.app = app

    def render(self) -> str:
        # The template doesn't have a extension so you can choose to use
        # the default template name but changing the response format from the
        # default, for example, using ".json" instead of ".html".
        template = (
            f"{self.resp.snake_controller}/"
            f"{self.resp.template}{self.resp.format}.jinja"
        )
        return self.app.render(template, **vars(self))

    def _dispatch(self, action: str) -> None:
        self.before_action(action, self.req.matched_params)
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

        resp.body = self.render()
