import hashlib
import inspect
import string
import typing as t
from importlib import import_module
from pathlib import Path

import inflection
import jinjax
from itsdangerous import (
    Signer,
    TimestampSigner,
    URLSafeTimedSerializer,
)

from proper import current, status
from proper.auth import Auth
from proper.cache import NoCache
from proper.cl import get_app_cl
from proper.errors import BadSecretKey, MatchNotFound, MethodNotAllowed
from proper.helpers import DotDict, jsonplus
from proper.i18n import I18n
from proper.request import Request
from proper.response import Response
from proper.router import Route, Router, get
from proper.storage import Storage
from proper.types import (
    TBody,
    TEventHandler,
    TEventHandlers,
    TException,
    THandler,
    TStartResponse,
    TWSGIEnvironment,
)

from . import pipeline
from .app_test import AppTest
from .config import get_default_config, get_env, logger
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)


if t.TYPE_CHECKING:
    from proper_cli import Cli


MIN_SECRET_LENGTH = 48


class App(AppTest):
    """
    A Proper app core.

    Arguments:

    - import_name:
        The name of the application package. Eg.: `foobar.web`.

    - config:
        Optional dict-like with the config.

    """

    # A lists of functions that are called if any of the functions in the
    # _on_before_dispatch, _on_dispatch, or _on_after_dispatch tuples
    # raises an exception.
    _on_error: TEventHandlers = ()

    # A lists of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown: TEventHandlers = ()

    # A lists of functions that are called when the development server starts,
    _on_dev_start: TEventHandlers = ()

    # A dict of functions to call when an HTTPError is raised.
    # The keys are any subclasses of Exception, but, not necessarily
    # subclasses of HTTPError.
    error_handlers: dict[TException, t.Any] = {}

    CL: "t.Type[Cli]"
    db: t.Any
    cache: t.Any

    def __init__(
        self,
        import_name: str,
        *,
        config: dict | None = None
    ) -> None:
        self.error_handlers = {}
        self._on_error = ()
        self._on_teardown = ()

        self._wrapped_wsgi = self.wsgi_app

        self._setup_paths(import_name)
        self._setup_config(config or {})
        self._setup_router()
        self._setup_serializer()
        self._setup_render()
        self._setup_cli()
        self._setup_auth()
        self._setup_i18n()
        self._setup_storage()

        self.cache = NoCache()

    def __call__(
        self,
        environ: TWSGIEnvironment,
        start_response: TStartResponse,
    ) -> TBody:
        return self._wrapped_wsgi(environ, start_response)

    @property
    def routes(self) -> list[Route]:
        return self.router._routes

    @routes.setter
    def routes(self, values: list[Route]) -> None:
        self.router.routes = values

    @property
    def components_path(self) -> Path:
        return self.root_path / self.config.COMPONENTS_FOLDER

    @property
    def static_path(self) -> Path:
        return self.root_path.parent / self.config.STATIC_FOLDER

    @property
    def locales_path(self) -> Path:
        return self.root_path.parent / self.config.LOCALES_FOLDER

    def on_error(self, func: TEventHandler) -> TEventHandler:
        """Decorator to add a function that runs if a request
        raises an exception."""
        self._on_error = self._on_error + (func,)
        return func

    def on_teardown(self, func: TEventHandler) -> TEventHandler:
        """Decorator to add a function that *always* run at the end of
        a request, even if an exception was raised before."""
        self._on_teardown = self._on_teardown + (func,)
        return func

    def on_dev_start(self, func: TEventHandler) -> TEventHandler:
        """Decorator to add a function that runs when the development
        server starts."""
        self._on_dev_start = self._on_dev_start + (func,)
        return func

    def on_dev_shutdown(self, func: TEventHandler) -> TEventHandler:
        """Decorator to add a function that runs when the development
        server is shutdown."""
        self._on_dev_shutdown = self._on_dev_shutdown + (func,)
        return func

    def wsgi_app(
        self,
        environ: TWSGIEnvironment,
        start_response: TStartResponse,
    ) -> TBody:
        current_response = self.do_request(environ)
        return current_response(start_response)

    def do_request(self, environ: TWSGIEnvironment) -> Response:
        current.app._set(self)

        current_request = Request(
            max_content_length=self.config.MAX_CONTENT_LENGTH,
            max_query_size=self.config.MAX_QUERY_SIZE,
            **environ,
        )
        current.request._set(current_request)

        current_response = Response(**environ)
        current.response._set(current_response)

        try:
            early_response = self.run_pipeline(current_request, current_response)
            return early_response or current_response

        except Exception as error:
            # We need this other `try...except` for handling any errors on:
            # - the custom error handlers,
            # - the functions in the `_on_teardown` or `_on_error` lists, or
            # - the body encoding on the `resp(start_response)`.
            current_response.error = error
            self._default_error_handler(current_request, current_response)
            return current_response

    def run_pipeline(self, request, response) -> None:
        try:
            for func in (
                pipeline.head_to_get,
                pipeline.method_override,
                pipeline.match,
                pipeline.redirect,
                pipeline.dispatch,
                pipeline.strip_body_if_head,
            ):
                early_response = func(self, request, response)
                if early_response is not None:
                    current.response._set(early_response)
                    return

        except Exception as error:
            response.error = error
            for func in self._on_error:
                func()
            self._handle_app_error(request, response)

        finally:
            for func in self._on_teardown:
                func()

    def error_handler(self, cls: TException, to: THandler) -> None:
        """Register a view method to handle errors by exception class.
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
        _anchor: str ="",
        **kw
    ) -> str:
        """Proxy for `self.router.url_for()`."""
        return self.router.url_for(name, object, _anchor=_anchor, **kw)

    def url_is(
        self,
        name: str,
        object: t.Any = None,
        *,
        curr_url: str ="",
        **kw
    ) -> bool:
        """Proxy for `self.router.url_is()`."""
        return self.router.url_is(name, object, curr_url=curr_url, **kw)

    def url_startswith(
        self,
        name: str,
        object: t.Any = None,
        *,
        curr_url: str ="",
        **kw
    ) -> bool:
        """Proxy for `self.router.url_startswith()`."""
        return self.router.url_startswith(name, object, curr_url=curr_url, **kw)

    def get_signer(self, namespace: str = "", **kwargs) -> Signer:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("key_derivation", "hmac")
        kwargs.setdefault("digest_method", hashlib.sha1)

        return Signer(self.config.SECRET_KEYS[0], **kwargs)

    def get_timestamp_signer(self, namespace: str = "", **kwargs) -> TimestampSigner:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("key_derivation", "hmac")
        kwargs.setdefault("digest_method", hashlib.sha1)

        return TimestampSigner(self.config.SECRET_KEYS[0], **kwargs)

    def get_serializer(self, namespace: str = "", **kwargs) -> URLSafeTimedSerializer:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("serializer", jsonplus)
        kwargs.setdefault("signer_kwargs", {})
        kwargs["signer_kwargs"].setdefault("key_derivation", "hmac")
        kwargs["signer_kwargs"].setdefault("digest_method", hashlib.sha1)

        return URLSafeTimedSerializer(self.config.SECRET_KEYS[0], **kwargs,)

    def get_current_locale(self) -> str | None:
        if not current.request:
            return None
        return current.request.locale

    def dev_start(self) -> None:
        for func in self._on_dev_start:
            func()

    # Private

    def _setup_paths(self, import_name: str) -> None:
        module = import_module(import_name)
        module_file = module.__file__
        assert module_file
        path = Path(module_file)
        if path.is_file():
            path = path.parent
        self.module = module
        self.root_path = path.resolve()
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

    def _setup_render(self) -> None:
        if not self.components_path.exists():
            self.catalog = None
            return

        self.catalog = jinjax.Catalog(
            root_url=self.config.COMPONENTS_URL,
            globals={
                "url_for": self.url_for,
                "url_is": self.url_is,
                "url_startswith": self.url_startswith,
            },
            fingerprint=True,
        )
        self.catalog.add_folder(self.components_path)

    def _setup_cli(self) -> None:
        self.CL = get_app_cl(self)

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

    def _setup_i18n(self) -> None:
        self.i18n = None

        if not self.config.LOCALES_FOLDER:
            return

        locales_path = self.locales_path
        if not locales_path.is_dir():
            return

        self.i18n = I18n(
            self.locales_path,
            get_current_locale=self.get_current_locale,
            default_locale=self.config.LOCALE_DEFAULT
        )

    def _setup_storage(self) -> None:
        if "STORAGE" not in self.config:
            return
        self.storage = Storage(self, self.config)

    def _handle_app_error(self, request, response) -> None:
        """Call the registered exception handler if exists or the fallback
        handlers if there isn't one for this error.
        """
        response.status = getattr(response.error, "status", status.server_error)

        # Do not call the custom error handlers while in DEBUG
        # Otherwise you would never see the debug pages.
        if self.config.DEBUG:
            self._default_error_handler(request, response)
            return

        if self.error_handlers:
            error = response.error
            for cls, handler in self.error_handlers.items():
                if isinstance(error, cls):
                    self._custom_error_handler(handler, request, response)
                    return

        self._default_error_handler(request, response)

    def _default_error_handler(self, request, response) -> None:
        response.status = getattr(response.error, "status", status.server_error)

        if not self.config.DEBUG and not self.config.CATCH_ALL_ERRORS:
            raise
        if self.config.DEBUG:
            self._default_error_handler_debug(request, response)
        else:
            self._default_error_handler_production(response)

    def _default_error_handler_debug(self, request, response) -> None:
        if isinstance(response.error, (MatchNotFound, MethodNotAllowed)):
            debug_not_found_handler(self, request, response)
        else:
            debug_error_handler(self, request, response)

    def _default_error_handler_production(self, response) -> None:
        if response.status in (status.not_found, status.gone):
            fallback_not_found_handler(response)
        elif response.status == status.forbidden:
            fallback_forbidden_handler(response)
        else:
            fallback_error_handler(response)

    def _custom_error_handler(self, handler, request, response) -> None:
        if request.matched_route:
            request.matched_route.to = handler
        else:
            request.matched_route = Route(method="", path="", to=handler)
        request.matched_params = {}
        pipeline.dispatch(self, request, response)
