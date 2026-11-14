"""Records each request of the app and adds the toolbar to its HTML pages."""
import functools
import logging
import re
import sys
import threading
import time
import types
import typing as t
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from hecto import JinjaRender

from proper.core.debug_info import MASK, hide_url_passwords, is_sensitive, safe_repr
from proper.core.error_handlers import redact_sensitive_info, redact_value
from proper.helpers import logger
from .record import (
    CacheCall,
    ComponentCall,
    LogLine,
    Query,
    Record,
    Render,
    Store,
    active,
)


if t.TYPE_CHECKING:
    from proper import App
    from proper.core.request import Request
    from proper.core.response import Response


#: Where the pages of the toolbar are served
URL_PREFIX = "/__debug__"

PACKAGE = Path(__file__).parent.resolve()
TEMPLATES = PACKAGE / "templates"

jinja_render = JinjaRender(TEMPLATES)
# The pages show data of the requests
jinja_render.env.autoescape = True

_BODY_END = "</body>"

#: The calls to the cache that are recorded. `get_or_set` is a `get` and,
#: after a miss, a `set`.
CACHE_OPS = (
    "get", "set", "delete", "increment", "decrement",
    "read_multi", "write_multi", "clear",
)
CACHE_READS = ("get", "read_multi")
#: Arguments of every view that are not its data. Those that start with
#: `_` are not either: `_globals`, the private attributes of the controller.
VIEW_INTERNALS = ("request", "response")
MAX_LOG_LINES = 500
#: How many redirects wait for the request that follows them
MAX_REDIRECTS = 20


def render(template: str, **data: t.Any) -> str:
    return jinja_render(template, url_prefix=URL_PREFIX, **data)


class Toolbar:
    def __init__(self, app: "App", *, size: int = 50) -> None:
        self.app = app
        self.enabled = True
        self.store = Store(size)
        # The files of the project, without those of its virtual environment
        self._project = str(app.root_path.parent) + "/"
        self._ignored_paths = tuple(self._ignored())
        cache_db = getattr(app.cache, "database", None)
        self._cache_dbs = {name for name, db in app.db.items() if db is cache_db}
        # `{path of the Location: ID of the request that redirected there}`
        self._redirects: dict[str, str] = {}
        self._lock = threading.Lock()

    def install(self) -> None:
        app = self.app
        # A bound method is not the plain function its type asks for
        app.around_request(t.cast(t.Any, self.around_request))
        for name, db in app.db.items():
            if db is not None:
                db.query_hooks.append(functools.partial(self.on_query, name))
        # On the instance: the class keeps the steps as they are
        app.pipeline = tuple(self._timed(step) for step in app.pipeline)
        for op in CACHE_OPS:
            setattr(app.cache, op, self._cache_call(op, getattr(app.cache, op)))
        app.catalog.tracer = self.trace_component
        # One for the process: it writes to the record of the request
        # being answered, whichever app answers it
        root = logging.getLogger()
        if not any(isinstance(handler, _LogHandler) for handler in root.handlers):
            root.addHandler(_LogHandler())

    def _ignored(self) -> t.Iterator[str]:
        yield URL_PREFIX
        assets = urlsplit(self.app.config.get("ASSETS_URL") or "").path
        if assets.strip("/"):
            yield "/" + assets.strip("/")

    def records(self, request: "Request") -> bool:
        if not self.enabled:
            return False
        path = request.path
        return not any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in self._ignored_paths
        )

    # Hooks

    def around_request(self, request: "Request", response: "Response", call_next):
        if not self.records(request):
            return call_next(request, response)

        record = Record(id=request.request_id, started_at=datetime.now())
        record.redirected_from = self._followed_redirect(request.get_url())
        active.set(record)
        start = time.perf_counter()
        try:
            response = call_next(request, response)
        finally:
            record.ms = (time.perf_counter() - start) * 1000
            active.set(None)
        try:
            self.finish(record, request, response)
            self.store.add(record)
            self.inject(record, response)
        except Exception:
            # A bug of the toolbar must not break the page it is added to
            logger.exception("debug toolbar")
        return response

    def on_query(self, db_name: str, event: t.Any) -> None:
        record = active.get()
        if record is None:
            return
        record.queries.append(
            Query(
                db=db_name,
                sql=str(event.sql),
                params=safe_repr(event.params) if event.params else "",
                ms=event.duration * 1000,
                error=_describe(event.exception),
                origin=self._origin(),
                cache=db_name in self._cache_dbs,
                component=record.rendering[-1].view if record.rendering else "",
            )
        )

    def _timed(self, step: types.FunctionType) -> types.FunctionType:
        @functools.wraps(step)
        def timed(request, response):
            record = active.get()
            if record is None:
                return step(request, response)
            start = time.perf_counter()
            try:
                return step(request, response)
            finally:
                ms = (time.perf_counter() - start) * 1000
                record.steps.append((step.__name__, ms))

        return t.cast(types.FunctionType, timed)

    def _cache_call(self, op: str, call: t.Callable) -> t.Callable:
        @functools.wraps(call)
        def recorded(*args, **kwargs):
            record = active.get()
            # A call made by another one (`read_multi` calls `get`) is part of it
            if record is None or _in_cache_call.get():
                return call(*args, **kwargs)
            token = _in_cache_call.set(True)
            start = time.perf_counter()
            hit = None
            try:
                result = call(*args, **kwargs)
                if op in CACHE_READS:
                    hit = bool(result) if op == "read_multi" else result is not None
                return result
            finally:
                ms = (time.perf_counter() - start) * 1000
                _in_cache_call.reset(token)
                record.cache_calls.append(
                    CacheCall(op=op, key=_cache_key(op, args), ms=ms, hit=hit)
                )

        return recorded

    def trace_component(self, relpath: str, render: t.Callable[..., str], kwargs: dict) -> str:
        """The `tracer` of the catalog: every component is rendered through it."""
        record = active.get()
        if record is None:
            return render(**kwargs)
        call = ComponentCall(view=relpath)
        stack = record.rendering
        stack.append(call)
        queries = len(record.queries)
        start = time.perf_counter()
        try:
            return render(**kwargs)
        finally:
            call.ms = (time.perf_counter() - start) * 1000
            call.queries = len(record.queries) - queries
            stack.pop()
            if stack:
                stack[-1].add(call)
            else:
                # The view itself: `catalog.render()` called it
                record.renders.append(
                    Render(
                        view=relpath,
                        ms=call.ms,
                        variables=self._variables(record, kwargs),
                        tree=call,
                    )
                )

    def _variables(self, record: Record, kwargs: dict) -> dict[str, str]:
        # Not recorded: a `repr()` can run a query or write a log line
        active.set(None)
        try:
            return _texts({
                name: value
                for name, value in kwargs.items()
                if name not in VIEW_INTERNALS and not name.startswith("_")
            })
        finally:
            active.set(record)

    def _followed_redirect(self, url: str) -> str:
        """The ID of the request that redirected to `url`, if one just did."""
        if not self._redirects:
            return ""
        with self._lock:
            return self._redirects.pop(url, "")

    def _remember_redirect(self, record: Record) -> None:
        with self._lock:
            self._redirects[record.redirect_to] = record.id
            while len(self._redirects) > MAX_REDIRECTS:
                del self._redirects[next(iter(self._redirects))]

    def _origin(self) -> str:
        """The closest line of the project that led to the query."""
        frame: t.Any = sys._getframe(2)
        project = self._project
        package = str(PACKAGE)
        while frame is not None:
            filename = frame.f_code.co_filename
            if (
                filename.startswith(project)
                and "/.venv/" not in filename
                and "/site-packages/" not in filename
                and not filename.startswith(package)
            ):
                path = filename[len(project):]
                return f"{path}:{frame.f_lineno} in {frame.f_code.co_name}"
            frame = frame.f_back
        return ""

    # After the request

    def finish(self, record: Record, request: "Request", response: "Response") -> None:
        """Copy what the pages show, as text: the store keeps no request,
        response, body or uploaded file."""
        record.method = request.request_method
        record.path = request.path
        record.url = request.get_url()
        record.status = response.status
        record.content_type = response.mimetype
        record.turbo_frame = request.turbo_frame or ""
        record.error = _describe(response.error)
        record.prefetch = request.headers.get("x-sec-purpose") == "prefetch"
        record.count_repeated()

        location = response.headers.get("location")
        if location and 300 <= response.status < 400:
            parts = urlsplit(str(location))
            record.redirect_to = f"{parts.path}?{parts.query}" if parts.query else parts.path
            self._remember_redirect(record)

        route = request.matched_route
        if route is not None:
            record.route_name = route.name or ""
            record.route_path = route.path or ""
            record.action = getattr(request, "matched_action", None) or ""
            if record.action:
                try:
                    record.controller = route.resolve()[0].__name__
                except Exception:
                    record.controller = ""

        record.request_data = [
            ("Route parameters", _texts(request.matched_params)),
            ("Query", _texts(_read(lambda: request.query))),
            ("Form", _texts(_read(lambda: request.form))),
            ("Headers", _texts(_read(lambda: request.headers))),
            ("Cookies", _texts(_read(lambda: request.cookies))),
            ("Session", _texts(request.session)),
        ]
        record.response_data = [
            ("Headers", _header_texts(response.get_headers_list())),
            ("Session", _texts(response.session)),
        ]

    def inject(self, record: Record, response: "Response") -> None:
        """Add the toolbar at the end of the body of an HTML page."""
        body = response.body
        if not isinstance(body, str) or response.mimetype != "text/html":
            return
        index = body.rfind(_BODY_END)
        if index == -1:
            # Not a whole page: a Turbo Frame, a fragment
            return
        previous = self.store.get(record.redirected_from) if record.redirected_from else None
        bar = render("bar.html", record=record, previous=previous)
        response.body = f"{body[:index]}{bar}{body[index:]}"


# Set while a call to the cache runs, in the thread of the request
_in_cache_call: ContextVar[bool] = ContextVar("debug_toolbar.in_cache_call", default=False)


class _LogHandler(logging.Handler):
    """Copies the log lines written while a request is answered to its
    record. It gets what the loggers let through: with `LOG_LEVEL = "info"`,
    not the debug lines of Proper."""

    def emit(self, record: logging.LogRecord) -> None:
        request_record = active.get()
        if request_record is None or len(request_record.logs) >= MAX_LOG_LINES:
            return
        try:
            message = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                error = _describe(record.exc_info[1])
                if error not in message:
                    message = f"{message}\n{error}" if message else error
            started = request_record.started_at.timestamp()
            request_record.logs.append(
                LogLine(
                    at=(record.created - started) * 1000,
                    level=record.levelname,
                    logger=record.name,
                    message=hide_url_passwords(message),
                )
            )
        except Exception:
            self.handleError(record)


def _cache_key(op: str, args: tuple) -> str:
    if op == "clear" or not args:
        return ""
    if op == "read_multi":
        return ", ".join(str(key) for key in args)
    if op == "write_multi":
        return ", ".join(str(key) for key in args[0])
    return str(args[0])


def _describe(error: BaseException | None) -> str:
    if error is None:
        return ""
    return f"{type(error).__name__}: {error}"


def _read(getter: t.Callable[[], t.Any]) -> t.Any:
    """A part of the request that may fail to parse."""
    try:
        return getter()
    except Exception:
        return None


def _texts(data: t.Any) -> dict[str, str]:
    """`data` as `{name: text}`, with the secrets redacted."""
    if not data:
        return {}
    try:
        data = redact_sensitive_info(dict(data))
    except Exception:
        return {}
    return {
        str(name): value if isinstance(value, str) else mask_repr(safe_repr(value))
        for name, value in data.items()
    }


_QUOTED = r"""(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")"""
# `name='value'` (an object) and `'name': 'value'` (a dict), in a `repr()`
_RX_REPR_SECRET = re.compile(
    rf"""(?:\b(?P<attr>\w+)=|['"](?P<key>[\w-]+)['"]:\s*)(?P<value>{_QUOTED})"""
)


def mask_repr(text: str) -> str:
    """`text`, the `repr()` of an object, without the secrets written in it
    as `password='...'` or `'password': '...'`: the `repr()` of a form has
    the values of its fields."""

    def mask(match: re.Match) -> str:
        name = match["attr"] or match["key"]
        if not is_sensitive(name):
            return match[0]
        return f"{match[0][: match.start('value') - match.start()]}{MASK!r}"

    return _RX_REPR_SECRET.sub(mask, text)


def _header_texts(headers: list[tuple[str, str]]) -> dict[str, str]:
    """The headers of the response; a repeated one (`Set-Cookie`) in lines."""
    texts: dict[str, str] = {}
    for name, value in headers:
        if is_sensitive(name) and value:
            value = redact_value(value)
        texts[name] = f"{texts[name]}\n{value}" if name in texts else value
    return texts
