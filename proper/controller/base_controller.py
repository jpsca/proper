"""A base controller class, all other application controllers must
inherit from. Stores data available to view/template.
"""
from ..constants import HEAD
from ..status import not_modified


__all__ = ("BaseController",)


class BaseController:

    _before_action = tuple()
    _after_action = tuple()

    def __init__(self, app):
        self._app = app

    def _dispatch(self, action, req, resp):
        filters = self._get_before_action_filters()
        self._apply_filters(filters, action, req, resp)
        if resp.stop:
            return

        if not resp.dispatched:
            self._call(action, req, resp)

        filters = self._get_after_action_filters()
        self._apply_filters(filters, action, req, resp)

    def _get_before_action_filters(self):
        filters = ()
        for cls in reversed(type.mro(self.__class__)):
            cls_filters = cls.__dict__.get("_before_action")
            if cls_filters:
                filters += cls_filters
        return filters

    def _get_after_action_filters(self):
        filters = ()
        for cls in type.mro(self.__class__):
            cls_filters = cls.__dict__.get("_after_action")
            if cls_filters:
                filters += cls_filters
        return filters

    def _apply_filters(self, filters, action, req, resp):
        for _filter in filters:
            if resp.stop:
                break
            if not self._should_apply_filter(_filter, action):
                continue
            func = _filter["filter"]
            if isinstance(func, str):
                func = getattr(self, func)
            func(req, resp)

    def _should_apply_filter(self, _filter, action):
        skip = _filter.get("skip")
        if skip and action in skip:
            return False
        only = _filter.get("only")
        if only and action not in only:
            return False
        return True

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
