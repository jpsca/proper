import hashlib
import inspect
import json
import string
import typing as t
from importlib import import_module
from pathlib import Path
from wsgiref.types import StartResponse, WSGIEnvironment

import inflection
import jinjax
from itsdangerous import (
    Signer,
    TimestampSigner,
    URLSafeTimedSerializer,
)
from markupsafe import Markup
from whitenoise import WhiteNoise

from . import pipeline, status
from .app_test import AppTest
from .config import get_env, get_default_config, logger
from .current import app, request, response
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from .auth import Auth
from .cli import get_app_cli
from .errors import MatchNotFound, MethodNotAllowed
from .helpers import DotDict, jsonplus
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


class BadSecretKey(Exception):
    pass


class App(AppTest):
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

    CL: "t.Type[Cli]"
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
        self._on_error = tuple()
        self._on_teardown = tuple()

        self._wrapped_wsgi = self.wsgi_app

        self._setup_paths(import_name)
        self._setup_config(config or {})
        self._setup_router()
        self._setup_serializer()
        self._setup_fallback_scheduler()
        self._load_static_manifest()
        self._setup_render()
        self._setup_whitenoise()
        self._setup_cli()
        self._setup_auth()
        self._setup_storage()

    def __call__(
        self,
        environ: WSGIEnvironment,
        start_response: StartResponse,
    ) -> t.Iterable[bytes]:
        return self._wrapped_wsgi(environ, start_response)

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

    def wsgi_app(
        self,
        environ: WSGIEnvironment,
        start_response: StartResponse,
    ) -> t.Iterable[bytes]:
        current_response = self.do_request(environ)
        return current_response(start_response)

    def do_request(self, environ: WSGIEnvironment) -> Response:
        app._set(self)

        current_request = Request(
            max_content_length=self.config.MAX_CONTENT_LENGTH,
            max_query_size=self.config.MAX_QUERY_SIZE,
            **environ,
        )
        request._set(current_request)

        current_response = Response(**environ)
        response._set(current_response)

        try:
            self.run_pipeline()
            return current_response

        except Exception as error:
            # We need this other `try...except` for handling any errors on:
            # - the custom error handlers,
            # - the functions in the `_on_teardown` or `_on_error` lists, or
            # - the body encoding on the `resp(start_response)`.
            current_response.error = error
            self._default_error_handler()
            return current_response

    def run_pipeline(self) -> None:
        try:
            for func in (
                pipeline.head_to_get,
                pipeline.method_override,
                pipeline.match,
                pipeline.redirect,
                pipeline.dispatch,
                pipeline.strip_body_if_head,
            ):
                early_response = func()
                if early_response is not None:
                    response._set(early_response)
                    return

        except Exception as error:
            response.error = error
            for func in self._on_error:
                func()
            self._handle_app_error()

        finally:
            for func in self._on_teardown:
                func()

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
        if self.config.DEBUG:
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
        host = host or self.config.STATIC_HOST or f"/{STATIC_PREFIX}"
        filename = filename.replace("..", ".").strip("/").strip("\\").strip()
        filename = self.static_manifest.get(filename, filename)
        return f"{host}/{filename}"

    def include_static(self, filename: str) -> str:
        """Read and returns a text file from the `static` folder, to include as-is.
        """
        text = (self.static_path / filename).read_text()
        return Markup(text)

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

        return Signer(self.config.SECRET_KEYS[0], **kwargs)

    def get_timestamp_signer(self, namespace: str = "proper", **kwargs) -> TimestampSigner:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("key_derivation", "hmac")
        kwargs.setdefault("digest_method", hashlib.sha1)

        return TimestampSigner(self.config.SECRET_KEYS[0], **kwargs)

    def get_serializer(self, namespace: str = "proper", **kwargs) -> URLSafeTimedSerializer:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("serializer", jsonplus)
        kwargs.setdefault("signer_kwargs", {})
        kwargs["signer_kwargs"].setdefault("key_derivation", "hmac")
        kwargs["signer_kwargs"].setdefault("digest_method", hashlib.sha1)

        return URLSafeTimedSerializer(self.config.SECRET_KEYS[0], **kwargs,)

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
        self.name = self.root_path.stem
        self.config_path = self.root_path / "config"

    def _setup_config(self, _config: dict) -> None:
        self.env = get_env()
        config = self._load_config()
        config.update(_config)
        self._validate_secret_keys(config.SECRET_KEYS)
        self.config = config

    def _load_config(self) -> DotDict:
        config = get_default_config()
        config_file = self.config_path / "app.py"
        if config_file.is_file():
            module = import_module(
                ".config.app", self.module.__package__
            )
            loaded_config = {
                name: getattr(module, name) for name in dir(module)
                if name[0] in string.ascii_uppercase
            }
            config.update(loaded_config)
        else:
            logger.warning(f"{config_file} cannot be imported")
        return config

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

    def _setup_router(self) -> None:
        self.router = Router()
        self.router._debug = self.config.DEBUG

    def _setup_serializer(self) -> None:
        self.serializer = self.get_serializer("proper.session")

    def _setup_fallback_scheduler(self) -> None:
        self.scheduler = HueyScheduler()

    def _load_static_manifest(self) -> None:
        path = self.static_manifest_path
        if not self.config.DEBUG and path.exists():
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
            autorefresh=self.config.DEBUG,
            immutable_file_test=RX_INMUTABLES_FILE,
        )

    def _setup_whitenoise(self) -> None:
        if not self.static_path.exists():
            return

        self._wrapped_wsgi = wn = WhiteNoise(
            self.wsgi_app,
            root=self.static_path,
            prefix=STATIC_PREFIX,
            autorefresh=self.config.DEBUG,
            immutable_file_test=RX_INMUTABLES_FILE,
        )
        for sp in self.config.STATIC_PATHS or []:
            path = self.root_path.parent / sp["path"].strip("/\\")
            prefix = sp["prefix"].lstrip("/\\")
            wn.add_files(path, prefix=prefix)

    def _setup_cli(self) -> None:
        self.CL = get_app_cli(self)

    def _setup_auth(self) -> None:
        if not self.config.AUTH_HASH_NAME:
            return
        logger.debug(f"AUTH_HASH_NAME is {self.config.AUTH_HASH_NAME}")
        config = self.config
        self.auth = Auth(
            secret_keys=config.SECRET_KEYS,
            hash_name=config.AUTH_HASH_NAME,
            rounds=config.AUTH_ROUNDS,
            password_minlen=config.AUTH_PASSWORD_MINLEN,
            password_maxlen=config.AUTH_PASSWORD_MAXLEN,
        )

    def _setup_storage(self) -> None:
        if "STORAGE" not in self.config:
            return
        self.storage = Storage(self, self.config)

    def _handle_app_error(self) -> None:
        """Call the registered exception handler if exists or the fallback
        handlers if there isn't one for this error.
        """
        response.status = getattr(response.error, "status", status.server_error)

        # Do not call the custom error handlers while in DEBUG
        # Otherwise you would never see the debug pages.
        if self.config.DEBUG:
            self._default_error_handler()
            return

        if self.error_handlers:
            error = response.error
            for cls, handler in self.error_handlers.items():
                if isinstance(error, cls):
                    self._custom_error_handler(handler)
                    return

        self._default_error_handler()

    def _default_error_handler(self) -> None:
        response.status = getattr(response.error, "status", status.server_error)

        if not self.config.DEBUG and not self.config.CATCH_ALL_ERRORS:
            raise
        if self.config.DEBUG:
            self._default_error_handler_debug()
        else:
            self._default_error_handler_production()

    def _default_error_handler_debug(self) -> None:
        if isinstance(response.error, (MatchNotFound, MethodNotAllowed)):
            debug_not_found_handler()
        else:
            debug_error_handler()

    def _default_error_handler_production(self) -> None:
        if response.status in (status.not_found, status.gone):
            fallback_not_found_handler()
        elif response.status == status.forbidden:
            fallback_forbidden_handler()
        else:
            fallback_error_handler()

    def _custom_error_handler(self, handler) -> None:
        if request.matched_route:
            request.matched_route.to = handler
        else:
            request.matched_route = Route(method="", path="", to=handler)
        request.matched_params = {}
        pipeline.dispatch()
