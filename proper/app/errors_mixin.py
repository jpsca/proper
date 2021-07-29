import inspect

from proper import status
from proper.errors import MatchNotFound
from proper.helpers import Dot
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from ..middleware.dispatch import dispatch


class ErrorsMixin:

    """A dict of functions to call when an HTTPError is raised.
    The keys are any subclasses of Exception, but, not necessarily subclasses
    of HTTPError."""

    error_handlers = None

    def errorhandler(self, cls, to):
        """Register a controller method to handle errors by exception class.

        Example:

        ```
        app.errorhandler(errors.NotFound, Pages.not_found)
        app.errorhandler(Exception, Pages.error)
        ```
        """
        assert inspect.isclass(cls) and issubclass(
            cls, Exception
        ), "`errorhandler` takes a subclass of `Exception` as first argument."
        self.error_handlers = self.error_handlers or {}
        self.error_handlers[cls] = to

    def _handle_app_error(self, req, resp):
        """Call the registered exception handler if exists or the fallback
        handlers if there isn't one for this error.
        """
        self._set_status_code(resp)

        # Do not call the custom error handlers while in DEBUG
        # Otherwise you would never see the debug pages.
        if self._config.debug:
            return self._default_error_handler(req, resp)

        if self.error_handlers:
            error = resp.error
            for cls, handler in self.error_handlers.items():
                if isinstance(error, cls):
                    return self._custom_error_handler(req, resp, handler)

        self._default_error_handler(req, resp)

    def _set_status_code(self, resp):
        error = resp.error
        resp.status_code = getattr(error, "status_code", status.server_error)

    def _default_error_handler(self, req, resp):
        self._set_status_code(resp)

        if not self._config.debug and not self._config.catch_all_errors:
            raise
        if self._config.debug:
            self._default_error_handler_debug(req, resp)
        else:
            self._default_error_handler_production(req, resp)

    def _default_error_handler_debug(self, req, resp):
        if isinstance(resp.error, MatchNotFound):
            debug_not_found_handler(req, resp, self)
        else:
            debug_error_handler(req, resp, self)

    def _default_error_handler_production(self, req, resp):
        if resp.status_code in (status.not_found, status.gone):
            fallback_not_found_handler(req, resp, self)
        elif resp.status_code == status.forbidden:
            fallback_forbidden_handler(req, resp, self)
        else:
            fallback_error_handler(req, resp, self)

    def _custom_error_handler(self, req, resp, handler):
        resp.template = None
        req.matched_route = Dot({"to": handler})
        req.matched_params = {}
        dispatch(req, resp, self)
