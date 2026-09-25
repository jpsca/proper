import asyncio
import contextvars
import copy
import hashlib
import logging
import os
import sys
import threading
import time
import types
import typing as t
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from pathlib import Path

import itsdangerous
import jx

from . import pipeline, status, tools
from .channels import Cable
from .cli.app_cli import get_cli
from .core.app_ws import AppWs
from .core.app_wsgi import AppWsgi
from .core.config import load_config
from .core.error_handlers import (
    debug_error_handler,
    debug_not_found_handler,
    fallback_error_handler,
    fallback_forbidden_handler,
    fallback_not_found_handler,
)
from .core.loop_debug import LoopWatchdog, enable_asyncio_debug
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
    from .core.request.request import TReadBody
    from .emails import BaseMailer
    from .i18n import I18n
    from .storage import _Attachment
    from .tools.mailer import Mailers


__all__ = ("App",)


# At most one "the pool is full" warning per this many seconds. A saturated
# pool would otherwise log once per queued request, and logging from the
# worker threads is the last thing it needs.
THREAD_WAIT_WARNING_INTERVAL = 10


def _split_address(address: str | None) -> "tuple[str, int | None] | None":
    """`"host:port"` as the server gives it, to `(host, port)`. IPv6 hosts
    come in brackets, which are dropped."""
    if not address:
        return None
    host, sep, port = address.rpartition(":")
    if not sep or not port.isdigit():
        return (address.strip("[]"), None)
    return (host.strip("[]"), int(port))


def _default_max_threads() -> int:
    """Python's own default for a `ThreadPoolExecutor`."""
    return min(32, (os.process_cpu_count() or 1) + 4)


class _ThreadWaits:
    """Counts requests that had to queue, and says when to report.

    Worker threads all call `record`, so the tally is locked.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0
        self._longest = 0.0
        self._reported_at = 0.0

    def record(self, waited: float, interval: float) -> "tuple[int, float] | None":
        """Note a wait. Returns `(count, longest)` when it is time to
        report, having reset the tally, and `None` while holding back."""
        with self._lock:
            self._count += 1
            self._longest = max(self._longest, waited)
            now = time.monotonic()
            if self._reported_at and now - self._reported_at < interval:
                return None
            self._reported_at = now
            report = (self._count, self._longest)
            self._count = 0
            self._longest = 0.0
            return report


class App(AppWs, AppWsgi):
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
    cable: Cable

    request_cls: type[Request] = Request
    response_cls: type[Response] = Response

    _loop_watchdog: LoopWatchdog | None = None
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
        self._thread_waits = _ThreadWaits()
        self._executor: ThreadPoolExecutor | None = None
        self._executor_lock = threading.Lock()
        self._executor_users = 0
        self._attachment_class_cache: "dict[type, type[_Attachment]]" = {}
        self._attachment_lock = threading.Lock()
        self._setup_paths(import_name)
        self.router = Router()
        self.CLI = get_cli(self)
        self._setup_serializers()

        for tool_module in self.tools:
            tool_module.setup(self)

        # This will pre-load all templates in the views folder
        # so any Jinja extension need to be setup before this line.
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

    # ---- RSGI ----
    #
    # The server (Granian) talks RSGI: one call per connection with a `scope`
    # describing it and a `protocol` to read the body and send the response
    # through, plus two hooks around the life of each worker.

    async def __rsgi__(self, scope, protocol) -> None:
        current.app = self
        if scope.proto == "http":
            await self._handle_http(scope, protocol)
        else:
            await self._handle_websocket(scope, protocol)

    def __rsgi_init__(self, loop: asyncio.AbstractEventLoop) -> None:
        loop.run_until_complete(self.startup())

    def __rsgi_del__(self, loop: asyncio.AbstractEventLoop) -> None:
        loop.run_until_complete(self.shutdown())

    async def startup(self) -> None:
        """Get ready to serve: the worker pool, the cable, the debug checks.
        Called once per server worker, all sharing this app."""
        logger.info("Application is starting up...")
        self._setup_executor()
        self._start_loop_debug()
        await self.cable.start()

    async def shutdown(self) -> None:
        """Undo `startup`."""
        logger.info("Application is shutting down...")
        await self.cable.stop()
        await self._stop_loop_debug()
        self._shutdown_executor()

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
        serializer using hte first secret key.

        With `timed=False` the token carries no timestamp, so it is
        deterministic (same input, same token) and can never expire. Read it
        back with `loads(..., timed=False)`.
        """
        serializers = self.serializers if timed else self.untimed_serializers
        return str(serializers[0].dumps(obj, salt=salt))

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
        `(value, timestamp)`, with timestamp returned as a naive
        `datetime.datetime` object in UTC.

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

    def _setup_executor(self) -> None:
        """Install the pool of threads that run the application's code.

        There is one pool per app, however many event loops share it: on
        free-threaded Python the server runs its workers as threads of one
        process, and each one calls this on its own loop. The pool is not
        made the loops' default executor on purpose, because a loop shuts
        its default executor down when it closes, and the first worker to
        stop would take the pool away from the rest. Every worker counts
        itself in here and out in `_shutdown_executor`.
        """
        with self._executor_lock:
            self._executor_users += 1
            if self._executor is None:
                self._executor = self._new_executor()
                logger.info("[app] %s worker threads", self.max_threads)

    def _shutdown_executor(self) -> None:
        """Let the pool go once the last worker that set it up is done."""
        with self._executor_lock:
            self._executor_users = max(0, self._executor_users - 1)
            if self._executor_users or self._executor is None:
                return
            executor = self._executor
            self._executor = None
        executor.shutdown(wait=False)

    def _new_executor(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(
            max_workers=self.max_threads,
            thread_name_prefix="proper-worker",
        )

    def _pool(self) -> ThreadPoolExecutor:
        """The shared pool, built on first use when no one set it up - a
        test client, or an app driven without the server's startup."""
        executor = self._executor
        if executor is None:
            with self._executor_lock:
                executor = self._executor
                if executor is None:
                    executor = self._executor = self._new_executor()
        return executor

    def _in_pool(self, func: "Callable", *args) -> "asyncio.Future":
        """Run `func` in the pool, carrying `current` and the rest of the
        context along - as `asyncio.to_thread` does - and return an
        awaitable for its result."""
        context = contextvars.copy_context()
        return asyncio.get_running_loop().run_in_executor(
            self._pool(), lambda: context.run(func, *args)
        )

    async def _run_in_worker(self, func: "Callable", *args) -> t.Any:
        """Run `func` in the worker pool.

        Every request spends its whole life in one of these threads, so
        when they are all busy the next request simply waits - invisibly,
        unless we say so.
        """
        threshold = self.config.THREAD_WAIT_WARNING
        if not threshold:
            return await self._in_pool(func, *args)

        submitted = time.monotonic()

        def start():
            waited = time.monotonic() - submitted
            if waited >= threshold:
                self._warn_thread_wait(waited)
            return func(*args)

        return await self._in_pool(start)

    def _warn_thread_wait(self, waited: float) -> None:
        """Report a queued request, at most once per interval."""
        report = self._thread_waits.record(
            waited, THREAD_WAIT_WARNING_INTERVAL
        )
        if report is None:
            return
        count, longest = report
        logger.warning(
            "[app] %s request(s) queued for a worker thread, up to %.1fs:"
            " all %s are busy. Raise MAX_THREADS, or move slow work"
            " to the queue.",
            count,
            longest,
            self.max_threads,
        )

    def _start_loop_debug(self) -> None:
        """In DEBUG, watch the event loop for work that should be running in
        a worker thread. Under `RUN_SYNC` the pipeline runs on the loop on
        purpose, so there is nothing to complain about.
        """
        threshold = self.config.LOOP_STALL_WARNING
        if not threshold or not self.config.DEBUG or self.config.get("RUN_SYNC"):
            return
        enable_asyncio_debug(threshold)
        self._loop_watchdog = LoopWatchdog(threshold)
        self._loop_watchdog.start()

    async def _stop_loop_debug(self) -> None:
        if self._loop_watchdog is not None:
            await self._loop_watchdog.stop()
            self._loop_watchdog = None

    def _warn_of_pending_migrations(self):
        if sys.argv[0].endswith("proper") and len(sys.argv) > 1 and sys.argv[1] == "db":
            return
        if self.has_migrations_pending():
            logger.warning(
                "There are pending migrations for this app. Run `proper db migrate` to apply them."
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

    def _request_from_scope(self, scope) -> Request:
        return self.request_cls(
            method=scope.method,
            path=scope.path,
            query_string=scope.query_string,
            headers=scope.headers.items(),
            scheme=scope.scheme,
            server=_split_address(scope.server),
            client=_split_address(scope.client),
            http_version=scope.http_version,
            app=self,
        )

    async def _handle_http(self, scope, protocol) -> None:
        if scope.method == "POST" and scope.path == self.config.CABLE_PATH:
            await self._receive_broadcast(scope, protocol)
            return
        request = self._request_from_scope(scope)
        response = await self._respond(request, protocol)
        await self._send_response(request, response, protocol)

    async def _respond(self, request: Request, read_body: "TReadBody") -> Response:
        """Run the request through the pipeline and return its response.

        `read_body` is an awaitable returning the request body as bytes:
        the RSGI protocol itself, or a stand-in from the `TestClient`.
        """
        current.request = request
        current.response = response = self.response_cls(self)
        try:
            await request._read_body(read_body)
        except Exception as error:
            response.error = error
            logger.debug(
                "Error while parsing request body: %s: %s",
                type(error).__name__,
                error,
            )
            # This error will be handled in the _run_pipeline method

        # By default the (synchronous) pipeline runs in a worker thread so it
        # doesn't block the event loop. `RUN_SYNC` runs it inline instead, on
        # the same thread/connection as the caller - which lets tests wrap a
        # request and its setup in a single DB transaction.
        if self.config.get("RUN_SYNC"):
            response = self._run_pipeline(request, response)
        else:
            response = await self._run_in_worker(
                self._run_pipeline, request, response
            )
        current.response = response
        return response

    async def _send_response(
        self, request: Request, response: Response, protocol
    ) -> None:
        status, headers, body = response.prepare(request)
        raw_body = response.body
        try:
            if isinstance(body, bytes):
                if body:
                    protocol.response_bytes(status, headers, body)
                else:
                    protocol.response_empty(status, headers)
                return

            if response.file_path is not None:
                # The server reads and sends the file itself, off the loop
                # and outside Python.
                protocol.response_file(status, headers, str(response.file_path))
                return

            # Any other iterable is streamed chunk by chunk. Reading it may
            # block, so each chunk is pulled in a worker thread: the loop
            # itself must never wait on a file or a slow generator.
            transport = await protocol.response_stream(status, headers)
            chunks = iter(body)
            while True:
                chunk = await self._in_pool(next, chunks, None)
                if chunk is None:
                    break
                await transport.send_bytes(bytes(chunk))
        finally:
            body_close = getattr(raw_body, "close", None)
            if callable(body_close):
                body_close()

    def _run_pipeline(self, request, response) -> Response:
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
