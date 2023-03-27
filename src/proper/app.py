import hashlib
import inspect
import json
import typing as t
from contextvars import ContextVar
from functools import partial
from importlib import import_module
from pathlib import Path

import inflection
import jinjax
from itsdangerous import (
    Signer,
    TimestampSigner,
    URLSafeTimedSerializer,
)
from markupsafe import Markup
from whitenoise import WhiteNoise

from . import middleware, status
from .config import get_env, get_default_config, logger
from .cryptex import Cryptex
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from .auth import Auth
from .cli_app import get_app_cli
from .errors import MatchNotFound, MethodNotAllowed
from .helpers import DotDict, jsonplus
from .middleware.dispatch import dispatch
from .request import Request
from .response import Response
from .router import Router, Route, get
from .scheduler import HueyScheduler
from .storage import Storage
from .assets import RX_INMUTABLES_FILE

if t.TYPE_CHECKING:
    from proper_cli import Cli


COMPONENTS_FOLDER = "components"
COMPONENTS_URL_ROOT = "/components/"
STATIC_PREFIX = "static"
STATIC_FOLDER = "static"
MANIFEST_PATH = "cache_manifest.json"
MIN_SECRET_LENGTH = 48
TException = t.Type[BaseException]

_request_cv = ContextVar("_request_cv", default=Request())
_response_cv = ContextVar("_response_cv", default=Response())


class BadSecretKey(Exception):
    pass


class App:
    # A lists of functions that are called before, during, and after dispatching
    # a request.
    # If one of these functions sets the stop attribute of the response,
    # the rest is skipped.
    _on_before_dispatch: tuple[t.Callable, ...] = tuple()
    _on_dispatch: tuple[t.Callable, ...] = tuple()
    _on_after_dispatch: tuple[t.Callable, ...] = tuple()

    # A lists of functions that are called if any of the functions in the
    # _on_before_dispatch, _on_dispatch, or _on_after_dispatch tuples
    # raises an exception.
    _on_error: tuple[t.Callable, ...] = tuple()

    # A lists of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown: tuple[t.Callable, ...] = tuple()

    # A lists of functions that are called when the development server starts,
    # and when it shutdown. Useful for running the scheduler on development and
    # similar tasks.
    _on_dev_start: tuple[t.Callable, ...] = tuple()
    _on_dev_shutdown: tuple[t.Callable, ...] = tuple()

    # A dict of functions to call when an HTTPError is raised.
    # The keys are any subclasses of Exception, but, not necessarily
    # subclasses of HTTPError.
    error_handlers: dict[TException, t.Any] = {}

    Cli: "t.Type[Cli]"
    db: t.Any
    scheduler: t.Any

    def __init__(
        self,
        import_name: str,
        *,
        config: dict | None = None
    ) -> None:
        """
        A Proper app core.

        Args:
            import_name:
                The name of the application package. Eg.: `foobar.web`.

            config:
                Optional dict-like with the config.

        """
        self.error_handlers = {}
        self._wrapped_wsgi = self.wsgi_app

        self._setup_paths(import_name)
        self._setup_config(config or {})
        self._setup_middleware()
        self._setup_router()
        self._setup_serializer()
        self._setup_fallback_scheduler()
        self._load_static_manifest()
        self._setup_render()
        self._setup_whitenoise()
        self._setup_cli()
        self._setup_auth()
        self._setup_storage()

    def __call__(self, environ: dict, start_response: t.Callable) -> t.Iterable[bytes]:
        return self._wrapped_wsgi(environ, start_response)

    @property
    def config(self) -> DotDict:
        return self._config

    @property
    def routes(self) -> list[Route]:
        return self.router._routes

    @routes.setter
    def routes(self, values: list[Route]) -> None:
        self.router.routes = values

    @property
    def components_path(self) -> Path:
        return self.root_path / COMPONENTS_FOLDER

    @property
    def static_path(self) -> Path:
        return self.root_path.parent / STATIC_FOLDER

    @property
    def static_manifest_path(self) -> Path:
        return self.static_path / MANIFEST_PATH

    def on_before_dispatch(self, func: t.Callable) -> t.Callable:
        """Decorator to add a function that runs before a request is dispatched"""
        self._on_before_dispatch = self._on_before_dispatch + (func,)
        return func

    def on_after_dispatch(self, func: t.Callable) -> t.Callable:
        """Decorator to add a function that runs after a request is dispatched"""
        self._on_after_dispatch = self._on_after_dispatch + (func,)
        return func

    def on_error(self, func: t.Callable) -> t.Callable:
        """Decorator to add a function that runs if a request
        raises an exception."""
        self._on_error = self._on_error + (func,)
        return func

    def on_teardown(self, func: t.Callable) -> t.Callable:
        """Decorator to add a function that *always* run at the end of
        a request, even if an exception was raised before."""
        self._on_teardown = self._on_teardown + (func,)
        return func

    def on_dev_start(self, func: t.Callable) -> t.Callable:
        """Decorator to add a function that runs when the development
        server starts. Useful for running the scheduler on development and
        similar tasks."""
        self._on_dev_start = self._on_dev_start + (func,)
        return func

    def on_dev_shutdown(self, func: t.Callable) -> t.Callable:
        """Decorator to add a function that runs when the development
        server is shutdown."""
        self._on_dev_shutdown = self._on_dev_shutdown + (func,)
        return func

    def wsgi_app(self, environ: dict, start_response: t.Callable) -> t.Iterable[bytes]:
        request = Request(
            max_content_length=self._config.max_content_length,
            max_query_size=self._config.max_query_size,
            **environ,
        )
        response = Response(
            _app=self,
            _request=request,
            **environ
        )

        _request_cv.set(request)
        _response_cv.set(response)
        if self.catalog:
            self.catalog.jinja_env.globals.update({
                "request": request,
                "response": response,
            })

        try:
            self.run_pipeline(request, response)
            return response(start_response)

        except Exception as error:
            # We need this other `try...except` for handling any errors on:
            # - the custom error handlers,
            # - the functions in the `_on_teardown` or `_on_error` lists, or
            # - the body encoding on the `resp(start_response)`.
            response.error = error
            self._default_error_handler(request, response)
            return response(start_response)

    def run_pipeline(self, request: Request, response: Response) -> None:
        try:
            for func in (
                self._on_before_dispatch + self._on_dispatch + self._on_after_dispatch
            ):
                func(request, response)
                if response.stop:
                    break

        except Exception as error:
            response.error = error
            for func in self._on_error:
                func(request, response)
            self._handle_app_error(request, response)

        finally:
            for func in self._on_teardown:
                func(request, response)

    def error_handler(self, cls: TException, to: t.Callable) -> None:
        """Register a controller method to handle errors by exception class.
        If debug=True, it also adds a route to preview that page.

        Example:

        ```python
        app.error_handler(errors.NotFound, Pages.not_found)
        app.error_handler(Exception, Pages.error)
        ```
        """
        is_exception = inspect.isclass(cls) and issubclass(cls, BaseException)
        assert is_exception, "`error_handler` takes a subclass of `Exception` as first argument."
        self.error_handlers[cls] = to
        if self._config.debug:
            qualname = getattr(cls, "__qualname__", "Exception")
            self.router.routes.append(
                get(f"_{inflection.underscore(qualname)}", to=to)
            )

    def url_for(
        self,
        name: str,
        object: t.Any = None,
        *,
        _anchor="",
        **kw
    ) -> str:
        """Proxy for `self.router.url_for()`."""
        return self.router.url_for(name, object=object, _anchor=_anchor, **kw)

    def url_static(self, filename: str, *, host: str | None = None) -> str:
        host = host or self._config.static.host or f"/{STATIC_PREFIX}"
        filename = filename.replace("..", ".").strip("/").strip("\\").strip()
        filename = self.static_manifest.get(filename, filename)
        return f"{host}/{filename}"

    def include_static(self, filename: str) -> str:
        """Read and returns a text file from the `static` folder, to include as-is.
        """
        text = (self.static_path / filename).read_text()
        return Markup(text)

    def edit_credentials(self, env: str) -> None:
        cryptex = Cryptex(self.credentials_path, env)
        cryptex.edit()

    def start(self) -> None:
        for func in self._on_dev_start:
            func()

    def shutdown(self) -> None:
        print("\nShutting down")
        for func in self._on_dev_shutdown:
            func()
        print("\n✨ Goodbye ✨")

    def get_signer(self, namespace: str = "proper", **kwargs) -> Signer:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("key_derivation", "hmac")
        kwargs.setdefault("digest_method", hashlib.sha1)

        return Signer(self._config.secret_keys[0], **kwargs)

    def get_timestamp_signer(self, namespace: str = "proper", **kwargs) -> TimestampSigner:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("key_derivation", "hmac")
        kwargs.setdefault("digest_method", hashlib.sha1)

        return TimestampSigner(self._config.secret_keys[0], **kwargs)

    def get_serializer(self, namespace: str = "proper", **kwargs) -> URLSafeTimedSerializer:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("serializer", jsonplus)
        kwargs.setdefault("signer_kwargs", {})
        kwargs["signer_kwargs"].setdefault("key_derivation", "hmac")
        kwargs["signer_kwargs"].setdefault("digest_method", hashlib.sha1)

        return URLSafeTimedSerializer(self._config.secret_keys[0], **kwargs,)

    # Private

    def _setup_paths(self, import_name: str) -> None:
        module = import_module(import_name)
        module_file = module.__file__
        assert module_file
        path = Path(module_file)
        if path.is_file():
            path = path.parent
        self.module = module
        self.root_path = path.absolute()
        self.config_path = self.root_path / "config"
        self.credentials_path = self.config_path / "credentials"

    def _setup_config(self, _config: dict) -> None:
        self.env = get_env()
        config = self._load_config()
        config.update(_config)
        credentials = self._load_credentials()
        config.update(credentials)
        self._validate_secret_keys(config.secret_keys)
        self._config = config

    def _load_config(self) -> DotDict:
        config = get_default_config()
        config_file = self.config_path / f"{self.env}.py"
        if config_file.is_file():
            env_config = import_module(
                f".config.{self.env}", self.module.__package__
            ).config
            config.update(env_config)
        else:
            logger.warning(f"{config_file} cannot be imported")
        return config

    def _load_credentials(self) -> DotDict:
        cryptex = Cryptex(self.credentials_path, self.env)
        credentials = cryptex.load()
        return DotDict(credentials)

    def _validate_secret_keys(self, secret_keys: list[str]) -> None:
        secret_keys = secret_keys or [""]
        for key in secret_keys:
            if len(key) < MIN_SECRET_LENGTH:
                raise BadSecretKey(
                    f"Your secret_key, `{key}` used for verifying the "
                    "integrity of signed cookies, is not secure enough. \n"
                    f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                    "and all random, no regular words or you'll be exposed to "
                    "dictionary attacks."
                )

    def _setup_middleware(self) -> None:
        self._on_before_dispatch = (
            partial(middleware.head_to_get, app=self),
            partial(middleware.method_override, app=self),
            partial(middleware.match, app=self),
            partial(middleware.redirect, app=self),
            partial(middleware.fetch_session, app=self),
        )
        self._on_dispatch = (partial(middleware.dispatch, app=self),)
        self._on_after_dispatch = (
            partial(middleware.put_session, app=self),
            partial(middleware.strip_body_if_head, app=self),
        )
        self._on_error = tuple()
        self._on_teardown = tuple()

        self.error_handlers = {}

    def _setup_router(self) -> None:
        self.router = Router()
        self.router._debug = self._config.debug

    def _setup_serializer(self) -> None:
        self.serializer = self.get_serializer("proper.session")

    def _setup_fallback_scheduler(self) -> None:
        self.scheduler = HueyScheduler(type="MemoryHuey", inmediate=True)

    def _load_static_manifest(self) -> None:
        path = self.static_manifest_path
        if not self._config.debug and path.exists():
            self.static_manifest = json.loads(path.read_text())
        else:
            self.static_manifest = {}

    def _setup_render(self) -> None:
        if not self.components_path.exists():
            self.catalog = None
            return

        self.catalog = jinjax.Catalog(
            root_url=COMPONENTS_URL_ROOT,
            globals={
                "url_for": self.url_for,
                "url_static": self.url_static,
                "include_static": self.include_static,
            },
        )
        self.catalog.add_folder(self.components_path)
        self._wrapped_wsgi = self.catalog.get_middleware(
            self.wsgi_app,
            autorefresh=self._config.debug,
            immutable_file_test=RX_INMUTABLES_FILE,
        )

    def _setup_whitenoise(self) -> None:
        if not self.static_path.exists():
            return

        self._wrapped_wsgi = wn = WhiteNoise(
            self.wsgi_app,
            root=self.static_path,
            prefix=STATIC_PREFIX,
            autorefresh=self._config.debug,
            immutable_file_test=RX_INMUTABLES_FILE,
        )
        for sp in self._config.static.paths or []:
            path = self.root_path.parent / sp["path"].strip("/\\")
            prefix = sp["prefix"].lstrip("/\\")
            wn.add_files(path, prefix=prefix)

    def _setup_cli(self) -> None:
        self.Cli = get_app_cli(self)

    def _setup_auth(self) -> None:
        if not self._config.auth:
            return
        config = self._config
        self.auth = Auth(
            secret_keys=config.secret_keys,
            hash_name=config.auth.hash_name,
            rounds=config.auth.rounds,
            password_minlen=config.auth.password_minlen,
            password_maxlen=config.auth.password_maxlen,
        )

    def _setup_storage(self) -> None:
        if not self._config.storage:
            return
        self.storage = Storage(self, self._config.storage)

    def _handle_app_error(self, request: Request, response: Response) -> None:
        """Call the registered exception handler if exists or the fallback
        handlers if there isn't one for this error.
        """
        self._set_status(response)

        # Do not call the custom error handlers while in DEBUG
        # Otherwise you would never see the debug pages.
        if self._config.debug:
            self._default_error_handler(request, response)
            return

        if self.error_handlers:
            error = response.error
            for cls, handler in self.error_handlers.items():
                if isinstance(error, cls):
                    self._custom_error_handler(request, response, handler)
                    return

        self._default_error_handler(request, response)

    def _set_status(self, response: Response) -> None:
        error = response.error
        response._status = getattr(error, "status", status.server_error)

    def _default_error_handler(self, request: Request, response: Response) -> None:
        self._set_status(response)

        if not self._config.debug and not self._config.catch_all_errors:
            raise
        if self._config.debug:
            self._default_error_handler_debug(request, response)
        else:
            self._default_error_handler_production(request, response)

    def _default_error_handler_debug(self, request: Request, response: Response) -> None:
        if isinstance(response.error, (MatchNotFound, MethodNotAllowed)):
            debug_not_found_handler(request, response, self)
        else:
            debug_error_handler(request, response, self)

    def _default_error_handler_production(self, request: Request, response: Response) -> None:
        if response._status in (status.not_found, status.gone):
            fallback_not_found_handler(request, response, self)
        elif response._status == status.forbidden:
            fallback_forbidden_handler(request, response, self)
        else:
            fallback_error_handler(request, response, self)

    def _custom_error_handler(self, request: Request, response: Response, handler) -> None:
        response.component = None
        if request.matched_route:
            request.matched_route.to = handler
        else:
            request.matched_route = Route(method="", path="", to=handler)
        request.matched_params = {}
        dispatch(request, response, self)
