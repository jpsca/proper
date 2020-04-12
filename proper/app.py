"""
## proper.app

"""
from pathlib import Path
from proper_config import ConfigDict

from . import middleware
from .app_errors_mixin import AppErrorsMixin
from .app_proxy_mixin import AppProxyMixin
from .constants import MIN_SECRET_LENGTH
from .default_config import DEFAULT_CONFIG
from .request import Request
from .response import Response
from .router import Router
from .support import Serializer


__all__ = ("App", "MissingSecretKey", "BadSecretKey")


class App(AppErrorsMixin, AppProxyMixin):
    serializer = None

    # Internal plugs.
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

    def __init__(
        self,
        root=None,
        *,
        debug=False,
        config=None,
        secrets=None,
        _controllers="controllers",
    ):
        """
            root (str):
                The root path of your application

            config (dict, path, list of paths and/or dicts, or None):
                Config file(s)

            secrets (dict, path, list of paths and/or dicts, or None):
                Encrypted secrets file(s)

            _controllers (str):
                Name of the module with the controllers, relative to the
                root of your application.

        """
        self.debug = debug
        self._set_root(root)
        self._set_controllers_mod(_controllers)
        self._config = ConfigDict(DEFAULT_CONFIG)
        self.router = Router()
        self.setup(config=config, secrets=secrets)

    @property
    def config(self):
        return self._config

    def _set_root(self, root):
        root = Path(root)
        if root.is_file():
            root = root.parent
        self.root = root

    def _set_controllers_mod(self, controllers):
        self.controllers_mod = self.root.name + "." + controllers

    def setup(self, config=None, *, secrets=None):
        self.load_config(_be_a_list(config), _be_a_list(secrets))
        self.config_router()
        if "secret_key" in self.config:
            self.init_serializer()

    def load_config(self, config=None, secrets=None):
        for file_or_dict in config:
            if isinstance(file_or_dict, dict):
                self._config.update(file_or_dict)
            else:
                self._config.load_file(file_or_dict)

        for file_or_dict in secrets:
            self._config.load_secrets(file_or_dict)

    def config_router(self):
        self.router.host = self._config.get("default_host", "localhost")
        self.router.root_path = self._config.get("root_path", "")
        self.router.use_ssl = self._config.get("use_ssl", False)
        self.router._debug = self.debug

    def init_serializer(self):
        secret_key = self.get_secret_key()
        self.serializer = Serializer(secret_key)

    def get_secret_key(self):
        secret_key = self._config.get("secret_key")

        if secret_key is None:
            raise MissingSecretKey(
                'Please add a "secret_key" to your secrets.\n'
                "Your secret key is needed for verifying the integrity of "
                "signed cookies. \n"
                f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                "and all random, no regular words or you'll be exposed to "
                "dictionary attacks. \n"
                "You can use `proper secret` to generate a secure secret key."
            )

        secret_key = str(secret_key)
        if len(secret_key) < MIN_SECRET_LENGTH:
            raise BadSecretKey(
                "Your secret_key, used for verifying the integrity of "
                "signed cookies, is not secure enough. \n"
                f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                "and all random, no regular words or you'll be exposed to "
                "dictionary attacks. \n"
                "You can use `proper secret` to generate a secure secret key."
            )

        return secret_key

    def get_serializer(self):
        if not self.serializer:
            self.init_serializer()
        return self.serializer

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
            self._run_pipeline(req, resp, self._pipeline)
            route = req.matched_route
            if route.forward_to:
                return route.forward_to(req.environ, req.start_response)
        except Exception as error:
            resp.error = error
            self._handle_app_errors(req, resp)
        finally:
            self._run_pipeline(req, resp, self._teardown)

    def _run_pipeline(self, req, resp, pipeline):
        for plug in pipeline:
            if resp.stop:
                return
            plug(req, resp, self)

    def test_server(self):
        from .server import run_server

        run_server(self, host="0.0.0.0", port=3030)

    def teardown(self, func):
        """Decorator to add a function to the `_teardown` tuple.
        """
        self._teardown = (self._teardown or ()) + (func, )
        return func


class MissingSecretKey(Exception):
    pass


class BadSecretKey(Exception):
    pass


class ControllersNotFound(Exception):
    pass


def _be_a_list(something):
    if something is None:
        return []
    if isinstance(something, (list, tuple)):
        return something
    return [something]
