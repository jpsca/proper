"""Logging with structlog.

`logger` is Proper's logger: a structlog logger that hands every event to
the `proper` logger of the standard library, with the `%s` arguments
still unformatted and the keyword arguments as the record's extra fields.

`setup_logging()` puts one handler on the root logger that writes the
records of every logger (Proper's, the app's, peewee's, huey's) through
structlog's processors: each line gets a timestamp, the level, the name
of the logger, and the variables bound with `structlog.contextvars`,
such as the `request_id` of the request being answered.
"""
import logging
import sys
import typing as t

import structlog


__all__ = (
    "LOG_FORMATS",
    "logger",
    "setup_logging",
)

LOG_FORMATS = ("console", "json", "off")
# Arguments of the stdlib logging methods; the other keys are extra fields
_LOG_KWARGS = ("exc_info", "stack_info", "stacklevel")


def _to_stdlib(
    _logger: t.Any, _method_name: str, event_dict: dict
) -> "tuple[tuple, dict]":
    """The arguments for the stdlib logging method, with the `%s` arguments
    unformatted: the stdlib formats them only if the level lets the record
    through."""
    args = (event_dict.pop("event", ""), *event_dict.pop("positional_args", ()))
    kwargs = {key: event_dict.pop(key) for key in _LOG_KWARGS if key in event_dict}
    if event_dict:
        kwargs["extra"] = event_dict
    return args, kwargs


_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "exception": logging.ERROR,
    "critical": logging.CRITICAL,
    "fatal": logging.CRITICAL,
}


class _BoundLogger(structlog.stdlib.BoundLogger):
    """Drops an event under the level of the logger before building it: a
    `logger.debug()` outside of debug mode costs as little as with the
    stdlib."""

    def _proxy_to_logger(
        self, method_name: str, event: str | None = None, *args: t.Any, **kw: t.Any
    ) -> t.Any:
        level = _LEVELS.get(method_name, logging.NOTSET)
        if not self._logger.isEnabledFor(level):
            return None
        return super()._proxy_to_logger(method_name, event, *args, **kw)


logger = _BoundLogger(logging.getLogger("proper"), processors=[_to_stdlib], context={})
logger.setLevel(logging.DEBUG)

_PRE_CHAIN = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.ExtraAdder(),
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]


class _StderrHandler(logging.StreamHandler):
    """Writes to `sys.stderr` as it is when the record comes, not as it was
    when the handler was made: something (a test runner) can replace it."""

    def __init__(self) -> None:
        logging.Handler.__init__(self)

    @property
    def stream(self) -> t.TextIO:  # type: ignore[override]
        return sys.stderr


_handler: _StderrHandler | None = None


def setup_logging(log_format: str) -> None:
    """Write the logs of every logger to stderr, in `log_format`:

    - `"console"`: one line per event, for people (with colors in a terminal).
    - `"json"`: one JSON object per line, for log collectors.
    - `"off"`: Proper adds no handler; configure `logging` yourself.

    Calling it again replaces the format of the handler it added.
    """
    global _handler
    root = logging.getLogger()
    if log_format == "off":
        if _handler is not None:
            root.removeHandler(_handler)
            _handler = None
        return

    if log_format == "json":
        processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # Without the variables of the frames: they can hold secrets
            structlog.processors.ExceptionRenderer(
                structlog.tracebacks.ExceptionDictTransformer(show_locals=False)
            ),
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # A plain traceback even if `rich` is installed, which would show
            # the variables of the frames
            structlog.dev.ConsoleRenderer(
                colors=sys.stderr.isatty(),
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=processors,
        foreign_pre_chain=_PRE_CHAIN,
    )
    if _handler is None:
        _handler = _StderrHandler()
        root.addHandler(_handler)
    _handler.setFormatter(formatter)
