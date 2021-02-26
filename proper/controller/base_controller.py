"""A base controller class, all other application controllers must
inherit from. Stores data available to view/template.
"""
from ..status import not_modified


__all__ = ("BaseController",)


class BaseController:

    def before_action(self, req, resp, action):
        pass

    def after_action(self, req, resp, action):
        pass

    def __init__(self, app):
        self._app = app

    def _dispatch(self, action, req, resp):
        self.before_action(req, resp, action)
        if resp.stop:
            return

        if not resp.dispatched:
            self._call(action, req, resp)

        self.after_action(req, resp, action)

    def _call(self, action, req, resp):
        # We call the endpoint but we do not expect a result value.
        # All the side effects of this call should be stored in the same
        # controller and in `resp`.
        method = getattr(self, action)
        method(req, resp, **req.matched_params)

        if resp.is_fresh:
            resp.status_code = not_modified
            resp.body = ""
            return

        if req.real_method == "HEAD" or resp.has_body or resp.stop:
            return

        resp.body = self._render(req, resp)

    def _render(self, req, resp):
        # The template doesn't have a extension so the action can choose to use
        # the default template name but changing the response format from the
        # default, for example, using ".json" instead of ".html".
        template = f"{resp.template}{resp.format}.jinja"
        return self._app.render(template, req=req, **self._as_dict())

    def _as_dict(self):
        return {
            name: getattr(self, name)
            for name in dir(self) if not name.startswith("_")
        }
