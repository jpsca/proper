import hashlib
import typing as t
from importlib import import_module
from pathlib import Path

import jinjax
from itsdangerous import (
    TimestampSigner,
    URLSafeTimedSerializer,
)

from proper import status
from proper.cache import FragmentCacheExtension
from proper.cl import get_app_cl
from proper.errors import MatchNotFound, MethodNotAllowed
from proper.helpers import jsonplus
from proper.helpers.utils import get_instance
from proper.i18n import I18n
from proper.request import Request
from proper.response import Response
from proper.router import Route, Router
from proper.storage import Storage
from proper.types import (
    TBody,
    TEventHandler,
    TEventHandlers,
    TStartResponse,
    TWSGIEnvironment,
)

from . import pipeline
from .app_test import AppTest
from .config import Config, get_env
from .current import current
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)


if t.TYPE_CHECKING:
    import peewee
    from proper_cli import Cli

    from proper.cache import BaseCache
    from proper.mail import EmailMessage
    from proper.queue import BaseQueue


__all__ = ("App", )


class App(AppTest):
    """
    A Proper app core.

    Arguments:
        import_name:
            The name of the application package. Eg.: `foobar.web`.
        config:
            Optional dict-like with the config.

    """

    # A lists of functions that are called if any of the functions in the
    # _on_before_dispatch, _on_dispatch, or _on_after_dispatch tuples
    # raises an exception.
    _on_error: TEventHandlers = ()

    # A lists of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown: TEventHandlers = ()

    name: str
    parent_path: Path
    root_path: Path
    views_path: Path
    config_path: Path
    static_path: Path
    locales_path: Path
    storage_path: Path

    router: Router
    config: Config
    CL: "t.Type[Cli]"
    db: "peewee.Database | None"
    cache: "BaseCache | None"
    queue: "BaseQueue | None"
    i18n: I18n | None
    storage: Storage | None
    catalog: jinjax.Catalog

    request_cls: t.Type[Request] = Request
    response_cls: t.Type[Response] = Response

    def __init__(
        self,
        import_name: str,
        config: t.Any = None,
    ) -> None:
        self._setup_paths(import_name)
        self._setup_router()
        self._setup_config(config or {})
        self._setup_serializer()
        self._setup_cli()
        self._setup_db()
        self._setup_cache()
        self._setup_queue()
        self._setup_mailer()
        self._setup_i18n()
        self._setup_storage()
        self._setup_render()

    def __call__(
        self,
        environ: TWSGIEnvironment,
        start_response: TStartResponse,
    ) -> TBody:
        return self.wsgi_app(environ, start_response)

    @property
    def routes(self) -> list[Route]:
        return self.router._routes

    @property
    def debug(self) -> bool:
        return self.config.DEBUG

    @debug.setter
    def debug(self, value: bool) -> None:
        self.config.DEBUG = value
        self.router.debug = value

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

    def wsgi_app(
        self,
        environ: TWSGIEnvironment,
        start_response: TStartResponse,
    ) -> TBody:
        current_response = self.do_request(environ)
        return current_response(start_response)

    def do_request(self, environ: TWSGIEnvironment) -> Response:
        current.app = self

        current.request = self.request_cls(
            max_content_length=self.config.MAX_CONTENT_LENGTH,
            max_query_size=self.config.MAX_QUERY_SIZE,
            **environ,
        )
        current.response = self.response_cls(**environ)

        try:
            self._db_connect()
            self.run_pipeline(current.request, current.response)
        except Exception as error:
            # We need this other `try...except` for handling any errors on:
            # - the custom error handlers,
            # - the functions in the `_on_teardown` or `_on_error` lists, or
            # - the body encoding on the `resp(start_response)`.
            current.response.error = error
            self._db_rollback()
            self._default_error_handler(current.request, current.response)
        finally:
            self._db_close()

        return current.response


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
                    current.response = early_response
                    return

        except Exception as error:
            response.error = error
            for func in self._on_error:
                func()
            self._handle_app_error(request, response)

        finally:
            for func in self._on_teardown:
                func()

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

    def get_signer(self, namespace: str = "", **kwargs) -> TimestampSigner:
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

    def send_email(self, later: bool = False, *args, **kwargs) -> t.Any:
        # TODO: later
        return self.mailer.send(*args, **kwargs)

    def send_emails(self, later: bool = False, *messages: "EmailMessage") -> t.Any:
        # TODO: later
        return self.mailer.send_emails(*messages)

    def get_current_locale(self) -> str | None:
        if not current.request:
            return None
        return current.request.locale

    # Private

    def _setup_paths(self, import_name: str) -> None:
        module = import_module(import_name)
        module_file = module.__file__
        assert module_file
        path = Path(module_file)
        if path.is_file():
            path = path.parent
        self.root_path = path.resolve()
        self.name = self.root_path.stem

        parent_path = self.root_path.parent
        self.views_path = self.root_path / "views"
        self.config_path = parent_path / "config"
        self.static_path = parent_path / "static"
        self.locales_path = parent_path / "locales"
        self.storage_path = parent_path / "storage"

    def _setup_config(self, user_config: t.Any) -> None:
        self.env = get_env()
        config = Config()
        config.update(user_config)
        config.validate()
        self.config = config

    def _setup_router(self) -> None:
        self.router = Router()

    def _setup_serializer(self) -> None:
        self.serializer = self.get_serializer("proper.session")

    def _setup_cli(self) -> None:
        self.CL = get_app_cl(self)

    def _setup_db(self) -> None:
        db_config = self.config.DATABASE.copy()
        if not db_config:
            self.db = None
            return
        if "migrations" in db_config:
            del db_config["migrations"]
        self.db = get_instance(**db_config)

    def _setup_queue(self) -> None:
        q_config = self.config.QUEUE.copy()
        if not q_config:
            self.queue = None
            return
        if "migrations" in q_config:
            del q_config["migrations"]
        self.queue = get_instance(**q_config)

    def _setup_cache(self) -> None:
        cache_config = self.config.CACHE.copy()
        if not cache_config:
            self.cache = None
            return
        self.cache = get_instance(**cache_config)

    def _setup_mailer(self) -> None:
        mailer_config = self.config.MAILER.copy()
        if not mailer_config:
            return
        self.mailer = get_instance(**mailer_config)

    def _setup_i18n(self) -> None:
        self.i18n = None

        if not self.locales_path.is_dir():
            return

        self.i18n = I18n(
            self.locales_path,
            get_current_locale=self.get_current_locale,
            default_locale=self.config.LOCALE_DEFAULT
        )

    def _setup_storage(self) -> None:
        if self.config.STORAGE is None:
            self.storage = None
            return
        assert self.config.STORAGE_SERVICES
        self.storage = Storage(self)

    def _setup_render(self) -> None:
        self.catalog = jinjax.Catalog(
            root_url=self.config.VIEWS_ASSETS_URL,
            globals={
                "url_for": self.url_for,
                "url_is": self.url_is,
                "url_startswith": self.url_startswith,
            },
            extensions=[
                FragmentCacheExtension,
            ],
            fingerprint=True,
        )
        self.catalog.add_folder(self.views_path)
        self.catalog.jinja_env.extend(app_cache=self.cache)

        if self.i18n:
            self.catalog.jinja_env.globals["_"] = self.i18n.translate

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

        error_handlers = self.router.error_handlers
        if error_handlers:
            error = response.error
            for error_cls, handler in error_handlers.items():
                if isinstance(error, error_cls):
                    self._custom_error_handler(handler, request, response)
                    return

        self._default_error_handler(request, response)

    def _default_error_handler(self, request, response) -> None:
        response.status = getattr(response.error, "status", status.server_error)

        if self.config.DEBUG:
            self._default_error_handler_debug(request, response)
        elif self.config.CATCH_ALL_ERRORS:
            self._default_error_handler_production(response)
        else:
            raise

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

    def _db_connect(self) -> None:
        if self.db is not None:
            self.db.connect()

        if self.queue is not None:
            qdb = getattr(self.queue, "database", None)
            if qdb is not None:
                qdb.connect()

        if self.cache is not None:
            cdb = getattr(self.cache, "database", None)
            if cdb is not None:
                cdb.connect()

    def _db_close(self) -> None:
        if self.db is not None and not self.db.is_closed():
            self.db.close()

        if self.queue is not None:
            qdb = getattr(self.queue, "database", None)
            if qdb is not None and not qdb.is_closed():
                qdb.close()

        if self.cache is not None:
            cdb = getattr(self.cache, "database", None)
            if cdb is not None and not cdb.is_closed():
                cdb.close()

    def _db_rollback(self):
        if self.db is not None and not self.db.is_closed():
            self.db.rollback()
