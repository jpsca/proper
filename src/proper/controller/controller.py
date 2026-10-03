"""A base controller class, all other application controllers
must inherit from. Stores data available to the views.
"""
import typing as t

from markupsafe import Markup
from minijx import ComponentNotFoundError

from ..compile.dispatch import callback_applies, plan_for, resolve_view
from ..constants import TURBO_STREAM_MIME
from ..helpers import MultiDict, jsonplus, logger, make_list
from ..status import not_acceptable, not_modified, unprocessable
from .template_resolver import formats_for


if t.TYPE_CHECKING:
    from ..app import App
    from ..core.request import Request
    from ..core.response import Response


class Controller:
    etag = ""

    def __init__(
        self,
        request: "Request",
        response: "Response",
    ) -> None:
        self.request = request
        self.response = response

    @property
    def app(self) -> "App":
        return self.request.app

    @property
    def params(self) -> MultiDict:
        if not hasattr(self, "_params"):
            params = MultiDict()
            params.update(self.request.query)
            params.update(self.request.form)
            params.update(self.request.matched_params or {})
            self._params = params
        return self._params

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
        status: int | None = None,
        json: t.Any = None,
        text: t.Any = None,
        stream: t.Any = None,
    ) -> str:
        if status is not None:
            self.response.status = status

        if stream is not None:
            self.response.mimetype = TURBO_STREAM_MIME
            parts = stream if isinstance(stream, (list, tuple)) else [stream]
            return Markup("".join(str(part) for part in parts))

        if json is not None:
            self.response.mimetype = "application/json"
            return jsonplus.dumps(json)

        if text is not None:
            self.response.mimetype = "text/plain"
            return text

        assert self.app.catalog
        return self.app.catalog.render(name, **vars(self))

    def redo(self, status: int = unprocessable):
        """A shortcut to re-render an invalid form"""
        action = self.request.matched_action
        target_action = "edit" if action == "update" else "new"
        inferred_view = self._resolve_view(target_action)
        self.response.body = self.render(inferred_view, status=status)

    # Private

    def _should_run_callback(self, options: dict[str, t.Any]) -> bool:
        return callback_applies(options, self.request.matched_action)

    def _run_callbacks(self, plan, callbacks, kind: str) -> bool:
        """Run the lowered `before` or `after` callbacks of `plan`. Returns
        `True` when a `before` callback produced a body, which ends the
        dispatch."""
        response = self.response
        for name, is_method in callbacks:
            attr = getattr(self, name)
            fns = (attr,) if is_method else make_list(attr)
            for fn in fns:
                if plan.log:
                    logger.debug(
                        "[%s.%s] %s: %s", plan.cls.__name__, plan.action, kind, name
                    )
                body = fn()
                if kind != "before":
                    continue
                if body is not None:
                    response.body = body
                if response.has_body:
                    if plan.log:
                        logger.debug(
                            "[%s.%s] halted by before callback: %s",
                            plan.cls.__name__, plan.action, name,
                        )
                    return True
        return False

    def _dispatch(self, action_name: str) -> "Response | None":
        plan = plan_for(type(self), action_name)
        if plan.before and self._run_callbacks(plan, plan.before, "before"):
            return
        self._call(action_name)
        if plan.after:
            self._run_callbacks(plan, plan.after, "after")

    def _call(self, action_name: str) -> None:
        # All the side effects of this call should be stored in the same
        # view and in `resp`.
        ret_value = getattr(self, action_name)()

        if self.response.is_fresh(request=self.request):
            self.response.status = not_modified
            self.response.body = ""
            return

        if ret_value is not None:
            self.response.body = ret_value
            return

        if not self.response.has_body:
            try:
                inferred_view = self._resolve_view(action_name)
            except ComponentNotFoundError:
                # Without a template in the default format either, the
                # template is missing: a bug, so it keeps failing.
                if not self._has_default_view(action_name):
                    raise
                # The action has a template, but not in a format the client
                # accepts. An error page keeps its status (e.g. 404).
                if self.response.status < 400:
                    self.response.status = not_acceptable
                self.response.body = ""
                return
            logger.debug(
                "[%s.%s] rendering inferred template: %s",
                self.__class__.__name__, action_name, inferred_view,
            )
            self.response.body = self.render(inferred_view)
            return

    def _resolve_view(self, action_name: str) -> str:
        request = self.request
        return self._find_view(
            action_name, formats_for(request.accept, request.default_format)
        )

    def _has_default_view(self, action_name: str) -> bool:
        try:
            self._find_view(action_name, (self.request.default_format,))
        except ComponentNotFoundError:
            return False
        return True

    def _find_view(self, action_name: str, formats: tuple[str, ...]) -> str:
        catalog = self.app.catalog
        assert catalog
        return resolve_view(
            plan_for(type(self), action_name),
            catalog,
            formats,
            # While templates can change on disk, the answer can change too.
            cache=catalog.auto_reload is False,
        )
