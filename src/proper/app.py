import asyncio
import hashlib
import types
import typing as t
from importlib import import_module
from pathlib import Path

import itsdangerous
import jx

from . import pipeline, status, tools
from .channels import Cable
from .cli.app_cli import get_cli
from .core.app_ws import AppWs
from .core.config import load_config
from .core.error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from .core.request import Request
from .core.response import Response
from .errors import MatchNotFound, MethodNotAllowed
from .global_context import current
from .helpers import DotDict, jsonplus, logger
from .router import Route, Router
from .storage import attachment_for
from .types import (
    THandler,
    TReceive,
    TScope,
    TSend,
)


if t.TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import peewee as pw
    from huey import Huey
    from proper_cli import Cli

    from .auth import Auth
    from .cache import BaseCache
    from .emails import BaseMailer
    from .i18n import I18n
    from .storage import _Attachment


__all__ = ("App",)


class App(AppWs):
    """
    A Proper app core.

    Arguments:
        import_name:
            The name of the application package. Eg.: `foobar.web`.
        config:
            Optional dict-like with the config.
        middleware:
            Optional list of ASGI middleware. Each middleware should be a
            callable that takes an ASGI app and returns a new ASGI app.

    """

    # A list of functions that are called if a request
    # raises an exception
    _on_error: tuple[THandler, ...] = ()

    # A list of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown: tuple[THandler, ...] = ()

    name: str
    root_path: Path
    views_path: Path
    config_path: Path
    assets_path: Path
    locales_path: Path
    storage_path: Path

    router: Router
    config: DotDict
    CLI: "type[Cli]"
    signers: tuple[itsdangerous.TimestampSigner, ...]
    serializers: tuple[itsdangerous.URLSafeTimedSerializer, ...]
    catalog: jx.Catalog

    pipeline: tuple[types.FunctionType, ...] = (
        pipeline.copy_session,
        pipeline.head_to_get,
        pipeline.method_override,
        pipeline.match,
        pipeline.redirect,
        pipeline.dispatch,
        pipeline.strip_body_if_head,
        pipeline.update_session_cookie,
    )

    tools: tuple[types.ModuleType, ...] = (
        tools.catalog,
        tools.cable,
        tools.db,
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
    auth: "Auth"
    i18n: "I18n | None"
    cable: Cable

    request_cls: type[Request] = Request
    response_cls: type[Response] = Response

    def __init__(
        self,
        import_name: str,
        config: dict[str, t.Any] | type | None = None,
        *,
        middleware: "Sequence[Callable]" = (),
    ) -> None:
        self.config = load_config(config or {})
        self._setup_paths(import_name)
        self.router = Router()
        self.CLI = get_cli(self)
        self._setup_serializers()

        for tool_module in self.tools:
            tool_module.setup(self)

        # This will pre-load all templates in the views folder
        # so any Jinja extension need to be setup before this line.
        self.catalog.add_folder(self.views_path)

        # Store the original asgi_app method before wrapping with middleware
        self._asgi_app = self.asgi_app
        for mw in reversed(middleware):
            self._asgi_app = mw(self._asgi_app)

        current.app = self

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
        await self._asgi_app(scope, receive, send)

    async def asgi_app(
        self,
        scope: TScope,
        receive: TReceive,
        send: TSend,
    ) -> None:
        scope["app"] = self
        current.app = self

        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    logger.info("Application is starting up...")
                    await self.cable.start()
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    logger.info("Application is shutting down...")
                    await self.cable.stop()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
                else:
                    logger.warning("Unknown lifespan message: %s", message["type"])

        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)

        elif scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)

    def url_for(
        self,
        name: str,
        object: t.Any = None,
        *,
        _anchor: str = "",
        _full: bool = False,
        **kw,
    ) -> str:
        """Proxy for `self.router.url_for()`."""
        return self.router.url_for(name, object, _anchor=_anchor, _full=_full, **kw)

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

    def dumps(self, obj: t.Any, salt: str | None = None) -> str:
        """Returns a signed string serialized with the internal
        serializer using hte first secret key.
        """
        return str(self.serializers[0].dumps(obj, salt=salt))

    def loads(
        self,
        value: str,
        *,
        max_age: int | None = None,
        return_timestamp: bool = False,
        salt: str | None = None,
    ) -> t.Any:
        """Reverse of `dumps`. Tries decoding the value with
        every secret key, in order, and returns `None` if the
        signature is outdated or not valid for any of the keys.

        If `return_timestamp` is `True` this method will return a tuple
        `(value, timestamp)`, with timestamp returned as a naive
        `datetime.datetime` object in UTC.
        """
        for serializer in self.serializers:
            try:
                return serializer.loads(
                    value, max_age=max_age, return_timestamp=return_timestamp, salt=salt
                )
            except itsdangerous.SignatureExpired:
                logger.debug("SignatureExpired %s...", str(value)[:10])
            except itsdangerous.BadSignature:
                logger.debug("BadSignature %s...", str(value)[:10])

    def on_error(self, func: THandler) -> THandler:
        """Decorator to add a function that runs if a request
        raises an exception."""
        self._on_error = self._on_error + (func,)
        return func

    def on_teardown(self, func: THandler) -> THandler:
        """Decorator to add a function that *always* run at the end of
        a request, even if an exception was raised before."""
        self._on_teardown = self._on_teardown + (func,)
        return func

    def attachment_for(self, base_model_cls: type) -> "type[_Attachment]":
        """Build an Attachment model subclass of `base_model_cls`.

        Used by the storage addon's seed `models/attachment.py`:

        ```python
        class Attachment(app.attachment_for(BaseModel)):
            ...
        ```

        The returned class carries all of the storage behavior (URLs, signed
        tokens, variants, purge, lookups) while inheriting `_meta.database`
        from `base_model_cls` - no separate `Meta` declaration needed on the
        consumer's class.

        Calls are memoized per-`(app, base_model_cls)` so repeated invocations
        return the same class. This keeps `VARIANTS_ENABLED_FOR` and the
        service-instance cache stable, and prevents accidentally creating
        duplicate peewee model classes for the same `attachment` table.
        """
        cache = self.__dict__.setdefault("_attachment_class_cache", {})
        if base_model_cls in cache:
            return cache[base_model_cls]
        cls = attachment_for(
            base_model_cls,
            app=self,
            default_service_name=self.config.get("STORAGE", ""),
        )
        cache[base_model_cls] = cls
        return cls

    # Private

    def _setup_paths(self, import_name: str) -> None:
        module = import_module(import_name)
        module_file = module.__file__
        if not module_file:
            raise ValueError(f"Cannot determine file path for module {import_name!r}")
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

    def _setup_serializers(self, namespace: str = "", **kwargs) -> None:
        kwargs["salt"] = namespace.encode()
        kwargs.setdefault("serializer", jsonplus)
        kwargs.setdefault("signer_kwargs", {})
        kwargs["signer_kwargs"].setdefault("key_derivation", "hmac")
        kwargs["signer_kwargs"].setdefault("digest_method", hashlib.sha256)

        self.serializers = tuple(
            itsdangerous.URLSafeTimedSerializer(secret_key, **kwargs)
            for secret_key in self.config.SECRET_KEYS
        )

    def _with_db(self, work, *, on_error=None) -> None:
        """Run `work()` with DB connections, error/teardown hooks, and cleanup.

        If `on_error` is provided, it is called with the exception when `work()`
        raises. If it is not provided, the exception propagates.

        If `on_error` itself raises (or a teardown hook raises), the DB is
        rolled back and the exception propagates to the caller.

        DB connections are always closed in the finally block.
        """
        try:
            try:
                self._dbs_connect()
                return work()
            except Exception as error:
                logger.debug(
                    "Error: %s: %s",
                    type(error).__name__,
                    error,
                )
                for func in self._on_error:
                    func()
                if on_error:
                    on_error(error)
                else:
                    raise
            finally:
                for func in self._on_teardown:
                    func()
        except Exception as error:
            logger.exception(
                "Unhandled error: %s: %s",
                type(error).__name__,
                error,
            )
            self._dbs_rollback()
            raise
        finally:
            self._dbs_close()

    async def _handle_http(
        self,
        scope: TScope,
        receive: TReceive,
        send: TSend,
    ) -> None:
        response = await self._do_request(scope, receive)
        status_code, headers, body = response.prepare()
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": headers,
            }
        )
        if isinstance(body, bytes):
            await send({"type": "http.response.body", "body": body})
        else:
            # Stream iterables (e.g. FileWrapper) in chunks
            try:
                for chunk in body:
                    await send(
                        {
                            "type": "http.response.body",
                            "body": chunk,
                            "more_body": True,
                        }
                    )
                await send({"type": "http.response.body", "body": b""})
            finally:
                body_close = getattr(body, "close", None)
                if callable(body_close):
                    body_close()

    async def _do_request(self, scope: TScope, receive: TReceive) -> Response:
        current.request = request = self.request_cls(scope)
        current.response = response = self.response_cls(scope)
        try:
            await request._parse_body(receive)
        except Exception as error:
            response.error = error
            logger.debug(
                "Error while parsing request body: %s: %s",
                type(error).__name__,
                error,
            )
            # This error will be handled in the _run_pipeline method

        response = await asyncio.to_thread(self._run_pipeline, request, response)
        current.response = response
        return response

    def _run_pipeline(self, request, response) -> Response:
        def work():
            if response.error:
                raise response.error
            for func in self.pipeline:
                logger.debug(
                    "[pipeline] %s %s -> %s",
                    request.request_method,
                    request.path,
                    func.__name__,
                )
                early_response = func(request, response)
                if early_response is not None:
                    logger.debug(
                        "[pipeline] %s returned early response",
                        func.__name__,
                    )
                    return early_response

        def on_error(error):
            response.error = error
            self._handle_app_error(request, response)

        try:
            early_response = self._with_db(work, on_error=on_error)
            if early_response is not None:
                return early_response
        except Exception as error:
            response.error = error
            self._default_error_handler(request, response)

        return response

    def _handle_app_error(self, request, response) -> None:
        """Call the registered exception handler if exists or the fallback
        handlers if there isn't one for this error.
        """
        logger.error(
            "[error] %s %s -> %s: %s",
            request.request_method,
            request.path,
            type(response.error).__name__,
            response.error,
        )

        # Do not call the custom error handlers while in DEBUG
        # Otherwise you would never see the debug pages.
        if not self.config.DEBUG:
            error_handlers = self.router.error_handlers
            if error_handlers:
                error = response.error
                for error_cls, handler in error_handlers.items():
                    if isinstance(error, error_cls):
                        response.status = getattr(
                            error,
                            "status",
                            status.server_error,
                        )
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
        pipeline.dispatch(request, response)

    def _dbs_op(self, op: str, *, when_closed: bool = False) -> None:
        for db in self.db.values():
            if db and not db.autoconnect and db.is_closed() == when_closed:
                getattr(db, op)()

    def _dbs_connect(self) -> None:
        self._dbs_op("connect", when_closed=True)

    def _dbs_close(self) -> None:
        self._dbs_op("close")

    def _dbs_rollback(self) -> None:
        self._dbs_op("rollback")
