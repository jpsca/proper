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
from structlog.typing import EventDict, WrappedLogger


__all__ = (
    "LOG_FORMATS",
    "LOG_LEVELS",
    "logger",
    "setup_logging",
)

LOG_FORMATS = ("console", "json", "off")
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}
# Arguments of the stdlib logging methods; the other keys are extra fields
_LOG_KWARGS = ("exc_info", "stack_info", "stacklevel")


def _to_stdlib(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
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

def _drop_formatted_fields(
    _logger: t.Any, _method: str, event_dict: dict[str, t.Any]
) -> dict[str, t.Any]:
    """Drop the fields that another handler's `logging.Formatter` writes on
    the record (`message`, `asctime`): they are not extra fields, and
    `extra=` can't use those names."""
    event_dict.pop("message", None)
    event_dict.pop("asctime", None)
    return event_dict


_PRE_CHAIN = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.ExtraAdder(),
    _drop_formatted_fields,
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


def _console_repr(value: t.Any) -> str:
    """A value as structlog's console shows it: a string as it is, unless
    it has a space, `=` or a quote; anything else with `repr()`."""
    if isinstance(value, str):
        if set(value) & {" ", "\t", "=", "\r", "\n", '"', "'"}:
            return repr(value)
        return value
    return repr(value)


def _console_renderer(colors: bool) -> structlog.dev.ConsoleRenderer:
    """The short console line, laid out as the server's access lines:

        19:53:02.464472Z [info]  Order paid  amount=10 order_id=42

    The time of day, the level (in color in a terminal) padded to the
    width of `[error]`, the event, and the other fields as `key=value`.
    The `request_id` is left out, and so is the logger's name when it is
    `proper`: `logger=peewee` stays.
    """
    Column = structlog.dev.Column
    level_styles = structlog.dev.ConsoleRenderer.get_default_level_styles(colors)
    reset = structlog.dev.RESET_ALL if colors else ""

    def level(_key: str, value: t.Any) -> str:
        style = level_styles.get(value, "") + (structlog.dev.BRIGHT if colors else "")
        return f"[{style}{value}{reset}]" + " " * max(0, len("error") - len(value))

    return structlog.dev.ConsoleRenderer(
        columns=[
            Column(
                "",
                structlog.dev.KeyValueColumnFormatter(
                    key_style="", value_style="", reset_style="", value_repr=_console_repr
                ),
            ),
            # "2026-10-24T19:53:02.464472Z" -> "19:53:02.464472Z"
            Column("timestamp", lambda _key, value: str(value)[11:]),
            Column("level", level),
            # The columns are joined by a space: this one adds the second
            # space before the fields (a line without them is stripped)
            Column("event", lambda _key, value: f"{value} "),
            Column("logger", lambda _key, value: "" if value == "proper" else f"logger={value}"),
            Column("request_id", lambda _key, _value: ""),
        ],
        # A plain traceback even if `rich` is installed, which would show
        # the variables of the frames
        exception_formatter=structlog.dev.plain_traceback,
    )


def setup_logging(log_format: str) -> None:
    """Write the logs of every logger to stderr, in `log_format`:

    - `"console"`: one short line per event, for people (in a terminal, the
      level in color).
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
            _console_renderer(colors=sys.stderr.isatty()),
        ]
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=processors,
        foreign_pre_chain=_PRE_CHAIN,
    )
    if _handler is None:
        _handler = _StderrHandler()
        root.addHandler(_handler)
    _handler.setFormatter(formatter)
