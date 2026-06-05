"""A base controller class, all other application controllers
must inherit from. Stores data available to the views.
"""
import typing as t

from ..helpers import MultiDict, jsonplus, logger, make_list
from ..status import not_modified, unprocessable
from .template_resolver import resolve_template


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

    def redo(self, status: int = unprocessable):
        """A shortcut to re-render an invalid form"""
        action = self.request.matched_action
        target_action = "edit" if action == "update" else "new"
        inferred_view = self._resolve_view(target_action)
        self.response.body = self.render(inferred_view, status=status)

    # Private

    def _should_run_callback(self, options: dict[str, t.Any]) -> bool:
        if not options:
            return True
        action = self.request.matched_action
        only = options.get("only", None)
        exclude = options.get("exclude", None)

        if only and action not in make_list(only):
            return False
        if exclude and action in make_list(exclude):
            return False
        return True

    def _dispatch(self, action_name: str) -> "Response | None":
        mro = type(self).mro()
        c_name = type(self).__name__

        for cls in reversed(mro):
            before = cls.__dict__.get("before", None)
            if before:
                for cb in make_list(before):
                    if self._should_run_callback(cb):
                        for action in make_list(getattr(self, cb["do"])):
                            logger.debug(
                                "[%s.%s] before: %s (from %s)",
                                c_name, action_name, cb["do"], cls.__name__,
                            )
                            body = action()
                            if body is not None:
                                self.response.body = body
                            if self.response.has_body:
                                logger.debug(
                                    "[%s.%s] halted by before callback: %s",
                                    c_name, action_name, cb["do"],
                                )
                                return

        self._call(action_name)

        for cls in mro:
            after = cls.__dict__.get("after", None)
            if after:
                for cb in make_list(after):
                    if self._should_run_callback(cb):
                        for action in make_list(getattr(self, cb["do"])):
                            logger.debug(
                                "[%s.%s] after: %s (from %s)",
                                c_name, action_name, cb["do"], cls.__name__,
                            )
                            action()

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
            inferred_view = self._resolve_view(action_name)
            logger.debug(
                "[%s.%s] rendering inferred template: %s",
                self.__class__.__name__, action_name, inferred_view,
            )
            self.response.body = self.render(inferred_view)
            return

    def _prefixes(self) -> list[str]:
        """View-folder prefixes to search, walking up the controller MRO.

        Subclass first, then each ancestor controller, stopping before
        `Controller` itself. Gives `application/` fallbacks and similar
        without any explicit config.
        """
        prefixes = []
        for cls in type(self).mro():
            if cls is Controller:
                break
            module = getattr(cls, "__module__", "")
            if not module or module.startswith("proper."):
                continue
            prefix = module.split(".", 2)[-1]
            prefix = prefix.removesuffix("_controller")
            prefix = prefix.replace(".", "/")
            if prefix not in prefixes:
                prefixes.append(prefix)
        return prefixes

    def _resolve_view(self, action_name: str) -> str:
        assert self.app.catalog
        return resolve_template(
            self.app.catalog,
            self._prefixes(),
            action_name,
            accept=self.request.accept,
            default_format=self.request.default_format,
            controller=type(self).__name__,
        )
