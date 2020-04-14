from . import middleware
from .app_errors_mixin import AppErrorsMixin
from .app_proxy_mixin import AppProxyMixin
from .app_setup_mixin import AppSetupMixin, MissingSecretKey, BadSecretKey
from .request import Request
from .response import Response


__all__ = ("App", "MissingSecretKey", "BadSecretKey")


class App(AppSetupMixin, AppErrorsMixin, AppProxyMixin):

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

    # A lists of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _teardown = tuple()

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
            # error handlers or the functions in the `_teardown` functions
            # might raise.
            resp.error = error
            self._handle_errors(req, resp)

        return resp(start_response)

    def call(self, req, resp):
        try:
            for plug in self._pipeline:
                plug(req, resp, self)
                if resp.stop:
                    break

            route = req.matched_route
            if route.forward_to:
                return route.forward_to(req.environ, req.start_response)

        except Exception as error:
            resp.error = error
            self._handle_app_errors(req, resp)

        finally:
            for plug in self._teardown:
                plug(req, resp, self)

    def teardown(self, func):
        """Decorator to add a function to the `_teardown` tuple.
        """
        self._teardown = (self._teardown or ()) + (func, )
        return func

    def test_server(self):
        from .server import run_server

        run_server(self, host="0.0.0.0", port=3030)
