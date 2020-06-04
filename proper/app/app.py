from proper import middleware
from proper.request import Request
from proper.response import Response

from .app_errors import AppErrors
from .app_setup import AppSetup, MissingSecretKey, BadSecretKey


__all__ = ("App", "MissingSecretKey", "BadSecretKey")


class App(AppSetup, AppErrors):

    # If one of these functions sets the stop attribute of the response,
    # the rest is skipped.
    _pipeline = (
        middleware.head_to_get,
        middleware.match,
        middleware.redirect,
        middleware.fetch_session,
        middleware.protect_from_forgery,

        middleware.dispatch,

        middleware.put_csrf_header,
        middleware.put_session,
        middleware.strip_body_if_head,
    )

    # A lists of functions that are all called if an exception is raised,
    # before any error handlers.
    _on_error = tuple()

    # A lists of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown = tuple()

    def __call__(self, environ, start_response):
        return self.wsgi(environ, start_response)

    def wsgi(self, environ, start_response):
        req = Request(environ, start_response, config=self.config)
        resp = Response()

        try:
            rv = self.call(req, resp)
            # If there is a return value, is the result of a
            # forward function that we must return right away.
            if rv is not None:
                return rv

        except Exception as error:
            # We need this other `try...except` for handling any errors the custom
            # error handlers or the functions in the `_on_teardown` or
            # `_on_error` functions might raise.
            resp.error = error
            self._handle_errors(req, resp)

        return resp(start_response)

    def call(self, req, resp):
        try:
            for func in self._pipeline:
                func(req, resp, self)
                if resp.stop:
                    break

            route = req.matched_route
            if route.forward_to:
                return route.forward_to(req.environ, req.start_response)

        except Exception as error:
            resp.error = error
            for func in self._on_error:
                func(req, resp, self)
            self._handle_app_errors(req, resp)

        finally:
            for func in self._on_teardown:
                func(req, resp, self)

    def on_error(self, func):
        """Decorator to add a function to the `_on_error` tuple.
        """
        self._on_error = (self._on_error or ()) + (func, )
        return func

    def on_teardown(self, func):
        """Decorator to add a function to the `_on_teardown` tuple.
        """
        self._on_teardown = (self._on_teardown or ()) + (func, )
        return func
