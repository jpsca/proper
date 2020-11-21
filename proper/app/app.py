from proper import middleware
from proper.local import current
from proper.request import Request
from proper.response import Response

from .app_errors import AppErrors
from .app_setup import AppSetup, MissingSecretKey, BadSecretKey  # noqa


__all__ = ("App", "MissingSecretKey", "BadSecretKey")


class App(AppSetup, AppErrors):

    # If one of these functions sets the stop attribute of the response,
    # the rest is skipped.
    _middleware = (
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

    @property
    def current_req(self):
        return getattr(current, "req", None)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        req = Request(environ, start_response, config=self.config)
        current.req = req
        resp = Response()

        try:
            self.run_middleware(req, resp)
            current.release()
            return resp(start_response)

        except Exception as error:
            # We need this other `try...except` for handling any errors on:
            # - the custom error handlers,
            # - the functions in the `_on_teardown` or `_on_error` lists, or
            # - the body encoding on the `resp(start_response)`.
            resp.error = error
            self._default_error_handler(req, resp)
            current.release()
            return resp(start_response)

    def run_middleware(self, req, resp):
        try:
            for func in self._middleware:
                func(req, resp, self)
                if resp.stop:
                    break

        except Exception as error:
            resp.error = error
            for func in self._on_error:
                func(req, resp, self)
            self._handle_app_error(req, resp)

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

    def url_for(self, name, *, _external=False, _anchor=None, **kwargs):
        """Proxy for `self.router.url_for()`."""
        return self.router.url_for(name, _external=_external, _anchor=_anchor, **kwargs)
