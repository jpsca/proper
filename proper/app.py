import inspect
import json
import logging
from contextvars import ContextVar
from functools import partial
from importlib import import_module
from pathlib import Path
from typing import Callable, Optional, Tuple

import inflection
from jinja2 import Markup
from sqla_wrapper import Alembic, SQLAlchemy
from whitenoise import WhiteNoise

from . import middleware, status
from .auth import Auth
from .cli_app import get_app_cli
from .config import get_env, get_default_config
from .constants import MIN_SECRET_LENGTH
from .cryptex import Cryptex
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from .errors import MatchNotFound
from .helpers import Dot, Render, Serializer
from .middleware.dispatch import dispatch
from .request import Request
from .response import Response
from .router import Router, get
from .scheduler import Scheduler
from .static import RX_INMUTABLES_FILE


__all__ = ("App", "BadSecretKey")

TEMPLATES_FOLDER = "templates"
STATIC_FOLDER = "static"
STATIC_PREFIX = "static"
PUBLIC_FOLDER = "public"
MANIFEST_PATH = "cache_manifest.json"

logger = logging.getLogger(__name__)
current = ContextVar("current", default=None)


class BadSecretKey(Exception):
    pass


class App:
    # If one of these functions sets the stop attribute of the response,
    # the rest is skipped.
    _on_before_dispatch: Tuple[Callable] = tuple()
    _on_dispatch: Tuple[Callable] = tuple()
    _on_after_dispatch: Tuple[Callable] = tuple()

    # A lists of functions that are called in any of the functions in the
    # _on_before_dispatch, _on_dispatch, or _on_after_dispatch tuples
    # raises an exception.
    _on_error: Tuple[Callable] = tuple()

    # A lists of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown: Tuple[Callable] = tuple()

    # A dict of functions to call when an HTTPError is raised.
    # The keys are any subclasses of Exception, but, not necessarily
    # subclasses of HTTPError.
    error_handlers = None

    serializer = None
    scheduler = None
    first_call = True

    def __init__(self, import_name, *, config=None):
        """
        import_name (str):
            The name of the application package. Eg.: `foobar.web`.

        config (dict):
            Optional dict-like with the config.

        """
        self._setup_paths(import_name)
        self._setup_config(config)
        self._setup_middleware()
        self._setup_router()
        self._setup_db()
        self._setup_serializer()
        self._setup_auth()
        self._setup_scheduler()
        self._setup_render()
        self._setup_whitenoise()
        self._setup_cli()

    def __call__(self, environ, start_response):
        if self.first_call:
            self.scheduler.start()
            self.first_call = False

        return self._wrapped_wsgi(environ, start_response)

    @property
    def config(self):
        return self._config

    @property
    def routes(self):
        return self.router._routes

    @routes.setter
    def routes(self, values):
        self.router.routes = values

    @property
    def templates_path(self):
        return self.root_path / TEMPLATES_FOLDER

    @property
    def static_path(self):
        return self.root_path.parent / STATIC_FOLDER

    @property
    def public_path(self):
        return self.static_path / PUBLIC_FOLDER

    @property
    def static_manifest_path(self):
        return self.static_path / MANIFEST_PATH

    @property
    def current_req(self) -> Optional[Request]:
        return current.get(None)

    def on_before_dispatch(self, func: Callable) -> Callable:
        """Decorator to add a function to the `_on_after_dispatch` tuple."""
        self._on_before_dispatch = self._on_before_dispatch + (func,)
        return func

    def on_after_dispatch(self, func: Callable) -> Callable:
        """Decorator to add a function to the `_on_after_dispatch` tuple."""
        self._on_after_dispatch = self._on_after_dispatch + (func,)
        return func

    def on_error(self, func: Callable) -> Callable:
        """Decorator to add a function to the `_on_error` tuple."""
        self._on_error = self._on_error + (func,)
        return func

    def on_teardown(self, func: Callable) -> Callable:
        """Decorator to add a function to the `_on_teardown` tuple."""
        self._on_teardown = self._on_teardown + (func,)
        return func

    def wsgi_app(self, environ, start_response):
        req = Request(
            max_content_length=self._config.max_content_length,
            max_query_size=self._config.max_query_size,
            **environ
        )
        token = current.set(req)
        resp = Response(_app=self, _req=req)

        try:
            self.run_pipeline(req, resp)
            current.reset(token)
            return resp(start_response)

        except Exception as error:
            # We need this other `try...except` for handling any errors on:
            # - the custom error handlers,
            # - the functions in the `_on_teardown` or `_on_error` lists, or
            # - the body encoding on the `resp(start_response)`.
            resp.error = error
            self._default_error_handler(req, resp)
            current.reset(token)
            return resp(start_response)

    def run_pipeline(self, req: Request, resp: Response) -> None:
        try:
            for func in (
                self._on_before_dispatch +
                self._on_dispatch +
                self._on_after_dispatch
            ):
                func(req, resp)
                if resp.stop:
                    break

        except Exception as error:
            resp.error = error
            for func in self._on_error:
                func(req, resp)
            self._handle_app_error(req, resp)

        finally:
            for func in self._on_teardown:
                func(req, resp)

    def error_handler(self, cls, to):
        """Register a controller method to handle errors by exception class.
        If debug=True, it also adds a route to preview that page.

        Example:

        ```
        app.error_handler(errors.NotFound, Pages.not_found)
        app.error_handler(Exception, Pages.error)
        ```
        """
        assert inspect.isclass(cls) and issubclass(
            cls, Exception
        ), "`error_handler` takes a subclass of `Exception` as first argument."
        self.error_handlers[cls] = to

        if self._config.debug:
            self.router.routes.append(
                get(f"_{inflection.underscore(cls.__qualname__)}", to=to)
            )

    def url_for(self, name: str, object=None, *, _anchor=None, **kwargs):
        """Proxy for `self.router.url_for()`."""
        return self.router.url_for(name, object=object, _anchor=_anchor, **kwargs)

    def url_static(self, filename, *, host=None):
        host = host or self._config.static.host or f"/{STATIC_PREFIX}"
        filename = filename.replace("..", ".").strip("/").strip("\\").strip()
        filename = self.static_manifest.get(filename, filename)
        return f"{host}/{filename}"

    def include_static(self, filename):
        """Read and returns a text file from the `static/public` folder, to include
        in the template as-is.
        """
        text = (self.public_path / filename).read_text()
        return Markup(text)

    def edit_credentials(self, env):
        cryptex = Cryptex(self.credentials_path, env)
        return cryptex.edit()

    def shutdown(self):
        print("\nShutting down")
        self.scheduler.shutdown(wait=True)
        print("\n✨ Goodbye ✨")

    # Private

    def _setup_paths(self, import_name):
        module = import_module(import_name)
        path = Path(module.__file__)
        if path.is_file():
            path = path.parent
        self.module = module
        self.root_path = path.absolute()
        self.config_path = self.root_path / "config"
        self.credentials_path = self.config_path / "credentials"

    def _setup_config(self, _config):
        self.env = get_env()
        config = self._load_config()
        config.update(_config)
        credentials = self._load_credentials()
        config.update(credentials)
        config.secret_key = self._validate_secret_key(config.secret_key)
        self._config = config

    def _load_config(self):
        config = get_default_config()
        config_file = self.config_path / f"{self.env}.py"
        if config_file.is_file():
            env_config = import_module(f".config.{self.env}", self.module.__package__).config
            config.update(env_config)
        else:
            logger.warning("%s cannot be imported", config_file)
        return config

    def _load_credentials(self):
        cryptex = Cryptex(self.credentials_path, self.env)
        return cryptex.load()

    def _validate_secret_key(self, secret_key):
        secret_key = str(secret_key or "")
        if len(secret_key) < MIN_SECRET_LENGTH:
            raise BadSecretKey(
                "Your secret_key, used for verifying the integrity of "
                "signed cookies, is not secure enough. \n"
                f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                "and all random, no regular words or you'll be exposed to "
                "dictionary attacks."
            )

        return secret_key

    def _setup_middleware(self):
        self._on_before_dispatch = (
            partial(middleware.head_to_get, app=self),
            partial(middleware.method_override, app=self),
            partial(middleware.match, app=self),
            partial(middleware.redirect, app=self),
            partial(middleware.fetch_session, app=self),
            partial(middleware.protect_from_forgery, app=self),
        )
        self._on_dispatch = (
            partial(middleware.dispatch, app=self),
        )
        self._on_after_dispatch = (
            partial(middleware.put_csrf_header, app=self),
            partial(middleware.put_session, app=self),
            partial(middleware.strip_body_if_head, app=self),
        )
        self._on_error = (
            self._rollback_db_session,
        )
        self._on_teardown = (
            self._remove_db_session,
        )

        self.error_handlers = {}

    def _setup_router(self):
        self.router = Router()
        self.router._debug = self._config.debug

    def _setup_db(self):
        config = self._config
        self.db = SQLAlchemy(
            dialect=config.database.dialect,
            name=config.database.name,
            user=config.database.user,
            password=config.database.password,
            host=config.database.host,
            port=config.database.port,
            engine_options=config.database.engine_options,
            session_options=config.database.session_options,
        )
        if config.database.migrations:
            self.alembic = Alembic(self.db, config.database.migrations)
        else:
            self.alembic = None

    def _setup_serializer(self):
        self.serializer = Serializer(self._config.secret_key)

    def _setup_auth(self):
        config = self._config
        self.auth = Auth(
            secret_key=config.secret_key,
            hash_name=config.auth.hash_name,
            rounds=config.auth.rounds,
            password_minlen=config.auth.password_minlen,
            password_maxlen=config.auth.password_maxlen,
        )

    def _setup_scheduler(self):
        self.scheduler = Scheduler()

    def _setup_render(self):
        self._load_static_manifest()
        self.render = Render(self.templates_path)
        self.render.globals["url_for"] = self.url_for
        self.render.globals["url_static"] = self.url_static
        self.render.globals["include_static"] = self.include_static

    def _load_static_manifest(self):
        path = self.static_manifest_path
        if not self._config.debug and path.exists():
            self.static_manifest = json.loads(path.read_text())
        else:
            self.static_manifest = {}

    def _setup_whitenoise(self):
        self._wrapped_wsgi = self.wsgi_app
        if not self.public_path.exists():
            return

        self._wrapped_wsgi = WhiteNoise(
            self.wsgi_app,
            root=self.public_path,
            prefix=STATIC_PREFIX,
            autorefresh=self._config.debug,
            immutable_file_test=RX_INMUTABLES_FILE,
        )
        for sp in (self._config.static.paths or []):
            path = self.root_path.parent / sp["path"].strip("/\\")
            prefix = sp["prefix"].lstrip("/\\")
            self._wrapped_wsgi.add_files(path, prefix=prefix)

    def _setup_cli(self):
        Cli = get_app_cli(self)
        self.cli = Cli()

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

    def _rollback_db_session(self, _req, _resp):
        self.db.s.rollback()

    def _remove_db_session(self, _req, _resp):
        self.db.s.remove()
