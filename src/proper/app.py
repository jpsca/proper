import asyncio
import hashlib
import typing as t
from importlib import import_module
from pathlib import Path

import jx
from itsdangerous import (
    TimestampSigner,
    URLSafeTimedSerializer,
)

from . import middleware, status, tools
from .app_test import AppTest
from .cache import FragmentCacheExtension
from .cli.app_cli import get_cli
from .config import load_config
from .error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from .errors import MatchNotFound, MethodNotAllowed
from .global_context import current
from .helpers import DotDict, jsonplus, logger
from .request import Request
from .response import Response
from .router import Route, Router
from .storage import Storage
from .types import (
    TEventHandler,
    TEventHandlers,
    TReceive,
    TScope,
    TSend,
)


if t.TYPE_CHECKING:
    import peewee as pw
    from huey import Huey
    from proper_cli import Cli

    from .cache import BaseCache
    from .emails import BaseMailer
    from .i18n import I18n


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

    # A lists of functions that are called if a request
    # raises an exception
    _on_error: TEventHandlers = ()

    # A lists of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown: TEventHandlers = ()

    name: str
    root_path: Path
    views_path: Path
    config_path: Path
    assets_path: Path
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
    mailer: "BaseMailer"
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
        self._setup_catalog()
        self._setup_tools()  # MUST be last

        # This will pre-load all templates in the views folder
        # so any Jinja extension need to be setup before this line.
        self.catalog.add_folder(self.views_path)

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

    async def __call__(
        self,
        scope: TScope,
        receive: TReceive,
        send: TSend,
    ) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    logger.info("Application is starting up...")
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    logger.info("Application is shutting down...")
                    await send({"type": "lifespan.shutdown.complete"})
                    return
                else:
                    logger.warning("Unknown lifespan message: %s", message["type"])
        elif scope["type"] == "http":
            await self.handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self.handle_websocket(scope, receive, send)

    async def handle_http(
        self,
        scope: TScope,
        receive: TReceive,
        send: TSend,
    ) -> None:
        response = await self.do_request(scope, receive)
        status, headers, body = response.prepare()
        # Send response back through ASGI
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

    async def do_request(self, scope: TScope, receive: TReceive) -> Response:
        scope["app"] = self
        current.app = self
        current.request = request = self.request_cls(scope)
        response = self.response_cls(scope)
        try:
            await request._parse_body(receive)
        except Exception as error:
            response.error = error
            logger.debug(
                "Error while parsing request body: %s: %s",
                type(error).__name__, error,
            )
            # This error will be handled in the run_pipeline method

        response = await asyncio.to_thread(self.run_pipeline, request, response)
        current.response = response
        return response

    def do_test_request(self, scope: TScope, body: bytes = b"") -> Response:
        """Synchronous request for testing. Body is already available as bytes."""
        scope["app"] = self
        current.app = self
        current.request = request = self.request_cls(scope)
        current.response = response = self.response_cls(scope)
        try:
            request._parse_body_bytes(body)
        except Exception as error:
            response.error = error
            logger.debug(
                "Error while parsing request body: %s: %s",
                type(error).__name__, error,
            )
        response = self.run_pipeline(request, response)
        current.response = response
        return response

    def run_pipeline(self, request, response) -> Response:
        try:
            try:
                if response.error:
                    raise response.error

                self._dbs_connect()
                for func in (
                    middleware.copy_session,
                    middleware.head_to_get,
                    middleware.method_override,
                    middleware.match,
                    middleware.redirect,
                    middleware.dispatch,
                    middleware.strip_body_if_head,
                    middleware.update_session_cookie,
                ):
                    logger.debug(
                        "[pipeline] %s %s -> %s",
                        request.request_method, request.path, func.__name__,
                    )
                    early_response = func(request, response)
                    if early_response is not None:
                        logger.debug(
                            "[pipeline] %s returned early response",
                            func.__name__,
                        )
                        return early_response

            except Exception as error:
                response.error = error
                logger.debug(
                    "[pipeline] error: %s: %s",
                    type(error).__name__, error,
                )
                for func in self._on_error:
                    func()
                self._handle_app_error(request, response)

            finally:
                for func in self._on_teardown:
                    func()

        except Exception as error:
            # For errors in the error handlers or teardown handlers
            logger.exception(
                "Unhandled error: %s: %s",
                type(error).__name__, error,
            )
            response.error = error
            self._dbs_rollback()
            self._default_error_handler(request, response)

        finally:
            self._dbs_close()

        return response

    async def handle_websocket(
        self,
        scope: TScope,
        receive: TReceive,
        send: TSend,
    ) -> None:
        pass

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
        kwargs["signer_kwargs"].setdefault("digest_method", hashlib.sha256)

        return URLSafeTimedSerializer(
            self.config.SECRET_KEYS[0],
            **kwargs,
        )

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

        self.views_path = self.root_path / "views"
        self.config_path = self.root_path / "config"
        self.assets_path = self.root_path / "assets"
        self.locales_path = self.config_path / "locales"
        self.storage_path = self.root_path.parent / "storage"

    def _setup_router(self) -> None:
        self.router = Router()

    def _setup_serializer(self) -> None:
        self.serializer = self.get_serializer("proper.session")

    def _setup_cli(self) -> None:
        self.CLI = get_cli(self)

    def _setup_catalog(self):
        self.catalog = jx.Catalog(
            extensions=[
                FragmentCacheExtension,
                *self.config.get("JINJA_EXTENSIONS", []),
            ],
            auto_reload=self.config.DEBUG,
            current=current,
            url_for=self.url_for,
            url_is=self.url_is,
            url_startswith=self.url_startswith,
        )

    def _setup_tools(self) -> None:
        for tool_module in self.tools:
            tool_module.setup(self)

    def _handle_app_error(self, request, response) -> None:
        """Call the registered exception handler if exists or the fallback
        handlers if there isn't one for this error.
        """
        response.status = getattr(response.error, "status", status.server_error)
        logger.error(
            "[error] %s %s -> %s: %s",
            request.request_method, request.path,
            type(response.error).__name__, response.error,
        )

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
            raise response.error

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
        middleware.dispatch(request, response)

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
