import inspect

from . import status
from .error_handlers import debug_error_handler
from .error_handlers import debug_not_found_handler
from .error_handlers import fallback_error_handler
from .error_handlers import fallback_forbidden_handler
from .error_handlers import fallback_not_found_handler
from .errors import MatchNotFound
from .support import objectify


class AppErrorsMixin(object):

    """A dict of functions to call when an HTTPError is raised.
    The keys are any subclasses of Exception, but, not necessarily subclasses
    of HTTPError."""

    error_handlers = None

    def errorhandler(self, cls, to):
        """Register a controller method to handle errors by exception class.
        """
        assert inspect.isclass(cls) and issubclass(
            cls, Exception
        ), "`errorhandler` takes a subclass of `Exception` as first argument."
        self.error_handlers = self.error_handlers or {}
        self.error_handlers[cls] = to

    def _handle_app_errors(self, req, resp):
        """Call the registered exception handler if exists or the fallback
        handlers if there isn't one for this error.
        """
        # Do not call the custom error handlers while in DEBUG
        # Otherwise you would never see the debug pages.
        if self.debug:
            return self._handle_errors(req, resp)

        error = resp.error
        resp.stop = True
        resp.status_code = getattr(error, "status_code", status.server_error)

        if self.error_handlers:
            for cls, handler in self.error_handlers.items():
                if isinstance(error, cls):
                    return self._call_custom_handler(handler, req, resp)

        self._handle_errors(req, resp)

    def _call_custom_handler(self, handler, req, resp):
        Controller, action = objectify(self.controllers_mod, handler)
        controller = Controller()
        method = getattr(controller, action)
        return method(req, resp, self)

    def _handle_errors(self, req, resp):
        if not self.debug and not self.config.catch_all_errors:
            raise

        error = resp.error
        resp.stop = True
        resp.status_code = getattr(error, "status_code", status.server_error)

        if self.debug:
            self._handle_errors_debug(req, resp)
        else:
            self._handle_errors_production(req, resp)

    def _handle_errors_debug(self, req, resp):
        if isinstance(resp.error, MatchNotFound):
            debug_not_found_handler(req, resp, self)
        else:
            debug_error_handler(req, resp, self)

    def _handle_errors_production(self, req, resp):
        if resp.status_code in (status.not_found, status.gone):
            fallback_not_found_handler(req, resp, self)

        elif resp.status_code == status.forbidden:
            fallback_forbidden_handler(req, resp, self)

        else:
            fallback_error_handler(req, resp, self)
