import hashlib
import typing as t
from importlib import import_module
from pathlib import Path

import jx
from itsdangerous import (
    TimestampSigner,
    URLSafeTimedSerializer,
)

from proper import status
from proper.cache import FragmentCacheExtension
from proper.cl.app_cl import get_cl
from proper.errors import MatchNotFound, MethodNotAllowed
from proper.helpers import DotDict, jsonplus
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
from . import pipeline, tools
from .app_test import AppTest
from .config import load_config
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from .global_context import g


if t.TYPE_CHECKING:
    import peewee as pw
    from huey import Huey
    from proper_cli import Cli

    from proper.cache import BaseCache
    from proper.i18n import I18n
    from proper.mail import EmailMessage, Mailer


__all__ = ("App",)


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
    config: DotDict
    CL: "type[Cli]"
    catalog: jx.Catalog

    tools: tuple[t.Any, ...] = (
        tools.db,  # must be first
        tools.queue,
        tools.cache,
        tools.mailer,
        tools.i18n,
        tools.auth,
        tools.storage,
    )

    db: "dict[str, pw.Database]"
    queue: "Huey"
    cache: "BaseCache"
    mailer: "Mailer"
    i18n: "I18n | None"
    storage: "Storage | None"

    request_cls: type[Request] = Request
    response_cls: type[Response] = Response

    def __init__(
        self,
        import_name: str,
        config: dict[str, t.Any] | type | None = None,
    ) -> None:
        self.config = load_config(config or {})
        self._setup_paths(import_name)
        self._setup_router()
        self._setup_serializer()
        self._setup_cli()
        self._setup_tools()
        self._setup_catalog()  # MUST be after tool setup

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
        value = bool(value)
        self.config.DEBUG = value
        self.router.debug = value
        self.catalog.auto_reload = value

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
        g.app = self

        g.request = request = self.request_cls(
            max_content_length=self.config.MAX_CONTENT_LENGTH,
            max_query_size=self.config.MAX_QUERY_SIZE,
            app=self,
            **environ,
        )
        g.response = response = self.response_cls(app=self, **environ)

        try:
            self._dbs_connect()
            self.run_pipeline(request, response)
        except Exception as error:
            # We need this other `try...except` for handling any errors on:
            # - the custom error handlers,
            # - the functions in the `_on_teardown` or `_on_error` lists, or
            # - the body encoding on the `resp(start_response)`.
            response.error = error
            self._dbs_rollback()
            self._default_error_handler(request, response)
        finally:
            self._dbs_close()

        return response

    def run_pipeline(self, request, response) -> None:
        try:
            for func in (
                pipeline.copy_session,
                pipeline.head_to_get,
                pipeline.method_override,
                pipeline.match,
                pipeline.redirect,
                pipeline.dispatch,
                pipeline.strip_body_if_head,
                pipeline.update_session_cookie,
            ):
                early_response = func(self, request, response)
                if early_response is not None:
                    g.response = early_response
                    return

        except Exception as error:
            response.error = error
            for func in self._on_error:
                func()
            self._handle_app_error(request, response)

        finally:
            for func in self._on_teardown:
                func()

    def url_for(self, name: str, object: t.Any = None, *, _anchor: str = "", **kw) -> str:
        """Proxy for `self.router.url_for()`."""
        return self.router.url_for(name, object, _anchor=_anchor, **kw)

    def url_is(
        self, name: str, object: t.Any = None, *, curr_url: str = "", **kw
    ) -> bool:
        """Proxy for `self.router.url_is()`."""
        return self.router.url_is(name, object, curr_url=curr_url, **kw)

    def url_startswith(
        self, name: str, object: t.Any = None, *, curr_url: str = "", **kw
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

        return URLSafeTimedSerializer(
            self.config.SECRET_KEYS[0],
            **kwargs,
        )

    def send_email(self, later: bool = False, *args, **kwargs) -> t.Any:
        # TODO: later
        return self.mailer.send(*args, **kwargs)

    def send_emails(self, later: bool = False, *messages: "EmailMessage") -> t.Any:
        # TODO: later
        return self.mailer.send_emails(*messages)

    def get_current_locale(self) -> str | None:
        if not g.request:
            return None
        return g.request.locale

    def get_current_timezone(self) -> str | None:
        if not g.request:
            return None
        return g.request.timezone

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

    def _setup_router(self) -> None:
        self.router = Router()

    def _setup_serializer(self) -> None:
        self.serializer = self.get_serializer("proper.session")

    def _setup_cli(self) -> None:
        self.CL = get_cl(self)

    def _setup_tools(self) -> None:
        for tool_module in self.tools:
            tool_module.setup(self)

    def _setup_catalog(self):
        jglobals: dict[str, t.Any] = {
            "url_for": self.url_for,
            "url_is": self.url_is,
            "url_startswith": self.url_startswith,
        }
        jfilters = {}

        if self.i18n:
            jglobals["_"] = self.i18n
            jfilters.update({
                "format_datetime": self.i18n.format_datetime,
                "format_date": self.i18n.format_date,
                "format_time": self.i18n.format_time,
                "format_timedelta": self.i18n.format_timedelta,
                "format_skeleton": self.i18n.format_skeleton,
                "format_list": self.i18n.format_list,
                "format_decimal": self.i18n.format_decimal,
                "format_compact_decimal": self.i18n.format_compact_decimal,
                "format_currency": self.i18n.format_currency,
                "format_compact_currency": self.i18n.format_compact_currency,
                "format_percent": self.i18n.format_percent,
                "format_scientific": self.i18n.format_scientific,
            })

        self.catalog = jx.Catalog(
            self.views_path,
            extensions=[
                FragmentCacheExtension,
            ],
            filters=jfilters,
            auto_reload=self.config.DEBUG,
            **jglobals,
        )
        self.catalog.jinja_env.extend(app_cache=self.cache)

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

    def _dbs_connect(self) -> None:
        for db in self.db.values():
            if db and not db.autoconnect and db.is_closed():
                db.connect()

    def _dbs_close(self) -> None:
        for db in self.db.values():
            if db and not db.autoconnect and not db.is_closed():
                db.close()

    def _dbs_rollback(self):
        for db in self.db.values():
            if db and not db.autoconnect and not db.is_closed():
                db.rollback()
