import copy
import functools
import hashlib
import logging
import os
import sys
import threading
import types
import typing as t
from importlib import import_module
from pathlib import Path

import itsdangerous
import minijx

from . import pipeline, status, tools
from .channels import BaseCable
from .cli.app_cli import get_cli
from .compile import install
from .core.app_wsgi import AppWsgi
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
)


if t.TYPE_CHECKING:
    from collections.abc import Callable

    import peewee as pw
    from huey import Huey
    from proper_cli import Cli

    from .auth import Auth
    from .cache import BaseCache
    from .emails import BaseMailer
    from .i18n import I18n
    from .storage import _Attachment
    from .tools.mailer import Mailers


__all__ = ("App",)


def _call_around(hook, call_next, request, response):
    """One link of the `around_request` chain."""
    return hook(request, response, call_next)


def _default_max_threads() -> int:
    """Python's own default for a `ThreadPoolExecutor`."""
    return min(32, (os.process_cpu_count() or 1) + 4)


class App(AppWsgi):
    """
    A Proper app core.

    Arguments:
        import_name:
            The name of the application package. Eg.: `foobar.web`.
        config:
            Optional dict-like with the config.

    """

    # A list of functions that are called if a request
    # raises an exception
    _on_error: tuple[THandler, ...] = ()

    # A list of functions that are all *always* called at the end of a request,
    # even if an exception was raised before.
    _on_teardown: tuple[THandler, ...] = ()

    # A list of functions that wrap the whole run of a request, and the
    # chain made of them, built once when they are added.
    _around_request: tuple[THandler, ...] = ()
    _wrapped_pipeline: "Callable[[Request, Response], Response] | None" = None

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
    catalog: minijx.Catalog

    pipeline: tuple[types.FunctionType, ...] = (
        pipeline.head_to_get,
        pipeline.method_override,
        pipeline.match,
        pipeline.redirect,
        pipeline.copy_session,
        pipeline.dispatch,
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
    mailers: "Mailers"
    auth: "Auth"
    i18n: "I18n | None"
    cable: BaseCable

    request_cls: type[Request] = Request
    response_cls: type[Response] = Response

    max_threads: int

    def __init__(
        self,
        import_name: str,
        config: dict[str, t.Any] | type | None = None,
    ) -> None:
        self.env = os.getenv("APP_ENV", "dev")
        self.import_name = import_name
        self.config = load_config(config or {})
        # Every `logger.debug` call builds a full record when the level lets
        # it through, handlers or not. Outside of debug mode that is pure cost
        # on the request path.
        logger.setLevel(logging.DEBUG if self.config.DEBUG else logging.INFO)
        self.max_threads = self.config.MAX_THREADS or _default_max_threads()
        self._attachment_class_cache: "dict[type, type[_Attachment]]" = {}
        self._attachment_lock = threading.Lock()
        self._setup_paths(import_name)
        self.router = Router()
        self.CLI = get_cli(self)
        self._setup_serializers()

        for tool_module in self.tools:
            tool_module.setup(self)

        # An app without views (an API) has no folder for them.
        if self.views_path.is_dir():
            self.catalog.add_folder(self.views_path)

        current.app = self

        self._warn_of_pending_migrations()

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

    def lower(self) -> None:
        """Take now every decision about dispatching that does not depend on
        the request, and compile every view (see `proper.compile`). Raises
        `LoweringError` for a callback that names a method its controller
        does not have, and, outside of debug mode, `minijx.CompileError`
        listing every view that does not compile; in debug mode those errors
        are logged, and each shows when its view is rendered."""
        install(self, strict=not self.config.DEBUG)

    def has_migrations_pending(self) -> bool:
        return False

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

    def dumps(self, obj: t.Any, salt: str | None = None, *, timed: bool = True) -> str:
        """Returns a signed string serialized with the internal
        serializer, using the newest secret key: the last one in
        `SECRET_KEYS`. `loads` accepts every key in the list, so a new key
        goes at the end and the oldest can be dropped later.

        With `timed=False` the token carries no timestamp, so it is
        deterministic (same input, same token) and can never expire. Read it
        back with `loads(..., timed=False)`.
        """
        serializers = self.serializers if timed else self.untimed_serializers
        return str(serializers[-1].dumps(obj, salt=salt))

    def loads(
        self,
        value: str,
        *,
        max_age: int | None = None,
        return_timestamp: bool = False,
        salt: str | None = None,
        timed: bool = True,
    ) -> t.Any:
        """Reverse of `dumps`. Tries decoding the value with
        every secret key, in order, and returns `None` if the
        signature is outdated or not valid for any of the keys.

        If `return_timestamp` is `True` this method will return a tuple
        `(value, timestamp)`, with the timestamp as a timezone-aware
        `datetime.datetime` in UTC.

        Use `timed=False` for values made with `dumps(..., timed=False)`.
        The two kinds are not interchangeable: each one rejects the other's
        tokens. `max_age` and `return_timestamp` need a timestamp, so they
        can't be combined with `timed=False`.
        """
        if not timed:
            if max_age is not None or return_timestamp:
                raise ValueError("Untimed values have no timestamp to check or return")
            for serializer in self.untimed_serializers:
                try:
                    return serializer.loads(value, salt=salt)
                except itsdangerous.BadData:
                    logger.debug("BadData %s...", str(value)[:10])
            return None

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

    def around_request(self, func: THandler) -> THandler:
        """Decorator to add a function that wraps the whole run of a request.

        It is called as `func(request, response, call_next)` and must return
        a response, normally the one from `call_next(request, response)`.
        Use it to do something before and after every request, like timing
        it or reporting it to a monitoring service.

        ```python
        @app.around_request
        def timer(request, response, call_next):
            start = time.perf_counter()
            response = call_next(request, response)
            print(request.path, time.perf_counter() - start)
            return response
        ```

        If the request failed, `response.error` has the exception, even
        when the app already showed an error page for it.

        The first function added is the outermost one.
        """
        self._around_request = self._around_request + (func,)
        call_next = self._run_pipeline_steps
        for hook in reversed(self._around_request):
            call_next = functools.partial(_call_around, hook, call_next)
        self._wrapped_pipeline = call_next
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
        # Requests run in threads, so two first calls for the same model can
        # overlap; without the lock each would build its own class and one of
        # them would end up with a duplicate peewee model for the same table.
        with self._attachment_lock:
            cls = self._attachment_class_cache.get(base_model_cls)
            if cls is None:
                cls = attachment_for(
                    base_model_cls,
                    app=self,
                    default_service_name=self.config.get("STORAGE", ""),
                )
                self._attachment_class_cache[base_model_cls] = cls
            return cls

    # ---- Private ----

    def _warn_of_pending_migrations(self):
        if sys.argv[0].endswith("proper") and len(sys.argv) > 1 and sys.argv[1] == "db":
            return
        if self.has_migrations_pending():
            logger.warning(
                "⚠️ [db]There are pending migrations for this app. Run `proper db migrate` to apply them."
            )

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
        self.assets_path = self.root_path.parent / "assets"
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
        # Same keys and signing parameters, but no timestamp in the token:
        # the same input always gives the same output. For values that never
        # expire anyway and benefit from being stable, like URLs that
        # browsers and CDNs should be able to cache.
        self.untimed_serializers = tuple(
            itsdangerous.URLSafeSerializer(secret_key, **kwargs)
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

    def _run_pipeline(self, request, response) -> Response:
        wrapped = self._wrapped_pipeline
        if wrapped is None:
            return self._run_pipeline_steps(request, response)
        return wrapped(request, response)

    def _run_pipeline_steps(self, request, response) -> Response:
        # Asked once here rather than on every step: each check is cheap,
        # but there are several per request.
        debug = logger.isEnabledFor(logging.DEBUG)

        def work():
            if response.error:
                raise response.error
            for func in self.pipeline:
                if debug:
                    logger.debug(
                        "[pipeline] %s %s -> %s",
                        request.request_method,
                        request.path,
                        func.__name__,
                    )
                early_response = func(request, response)
                if early_response is not None:
                    if debug:
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
            "❌ %s %s -> %s: %s",
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
                        self._custom_error_handler(handler, request, response)
                        return

        self._default_error_handler(request, response)

    def _default_error_handler(self, request, response) -> None:
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
        # `matched_route` is the registered Route object shared by every request,
        # so it must not be mutated: dispatch through a copy that points at the
        # handler instead.
        if request.matched_route:
            request.matched_route = copy.copy(request.matched_route)
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
