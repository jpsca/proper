"""
What the debug error pages show of an error: the frames of its traceback,
told apart into those of the app and those of Proper and the libraries,
with their code and variables, and the same as plain text.
"""

import linecache
import re
import reprlib
import sysconfig
import typing as t
from dataclasses import dataclass, field
from pathlib import Path


if t.TYPE_CHECKING:
    from types import FrameType, TracebackType


__all__ = (
    "ErrorInfo",
    "Frame",
    "describe_request",
    "format_text",
    "get_errors",
    "hide_url_passwords",
    "is_sensitive",
    "safe_repr",
)


#: Lines of code shown before and after the line of a frame of the app.
CONTEXT_BEFORE = 3
CONTEXT_AFTER = 2

#: Shown instead of a secret, or of a message that raises.
MASK = "▒" * 4

#: Config keys, variables, form fields and headers that end with one of
#: these (in any letter case, with `-` read as `_`) hold secrets.
SENSITIVE_SUFFIXES = (
    "PASSWORD",
    "PASSWD",
    "SECRET",
    "SECRETS",
    "SECRET_KEY",
    "SECRET_KEYS",
    "TOKEN",
    "API_KEY",
    "APIKEY",
    "ACCESS_KEY",
    "PRIVATE_KEY",
    "CREDENTIALS",
    "COOKIE",
    "AUTHORIZATION",
)

#: The password of a URL, like `postgres://user:password@host/db`.
RX_URL_PASSWORD = re.compile(r"([a-z][a-z0-9+.-]*://[^:/@\s'\"]*:)[^@/\s'\"]+@", re.IGNORECASE)

PROPER_PATH = str(Path(__file__).parents[1]) + "/"
LIBRARY_PATHS = tuple(
    {
        str(Path(path)) + "/"
        for name in ("stdlib", "platstdlib", "purelib", "platlib")
        if (path := sysconfig.get_paths().get(name))
    }
)

_repr = reprlib.Repr(
    maxlevel=3,
    maxlist=10,
    maxtuple=10,
    maxset=10,
    maxdict=10,
    maxstring=160,
    maxother=160,
)


@dataclass
class Frame:
    #: The path of the file, relative to the current folder if it is in it.
    path: str
    lineno: int
    name: str
    #: The line of the frame, without indentation.
    line: str
    #: `(lineno, text)` of the lines around it; only for frames of the app.
    context: list[tuple[int, str]] = field(default_factory=list)
    #: `name: repr()` of its variables; only for frames of the app.
    variables: dict[str, str] = field(default_factory=dict)
    is_app: bool = True
    filename: str = field(default="", repr=False)
    tb_frame: "FrameType | None" = field(default=None, repr=False, compare=False)


@dataclass
class ErrorInfo:
    #: The full name of the class of the error, like `KeyError`.
    type: str
    message: str
    frames: list[Frame]
    #: How it is chained to the next, newer, error of the chain: `"cause"`
    #: (`raise ... from` it), `"context"` (raised while handling it), or `""`.
    chain: str = ""

    @property
    def summary(self) -> str:
        return f"{self.type}: {self.message}" if self.message else self.type

    @property
    def where(self) -> Frame | None:
        """The last frame of the app: where the error happened, as far as
        the code of the app goes."""
        for frame in reversed(self.frames):
            if frame.is_app:
                return frame
        return None

    def groups(self) -> list[Frame | list[Frame]]:
        """The frames, with each run of frames that are not of the app
        together in a list."""
        groups: list[Frame | list[Frame]] = []
        run: list[Frame] | None = None  # the frames not of the app, so far
        for frame in self.frames:
            if frame.is_app:
                groups.append(frame)
                run = None
            elif run is None:
                run = [frame]
                groups.append(run)
            else:
                run.append(frame)
        return groups


def is_sensitive(name: t.Any) -> bool:
    """Whether a config key, variable, form field or header of this name
    holds a secret."""
    if not isinstance(name, str):
        return False
    return name.upper().replace("-", "_").endswith(SENSITIVE_SUFFIXES)


def hide_url_passwords(text: str) -> str:
    return RX_URL_PASSWORD.sub(rf"\g<1>{MASK}@", text)


def safe_repr(value: t.Any) -> str:
    """A short `repr()` of `value`, without the passwords of the URLs in
    it. A value whose `repr()` raises is shown as `<Class instance at 0x...>`."""
    return hide_url_passwords(_repr.repr(value))


def get_errors(error: BaseException) -> list[ErrorInfo]:
    """The error and those chained to it, oldest first, as Python prints
    them."""
    chain: list[tuple[BaseException, str]] = []
    seen: set[int] = set()
    current: BaseException | None = error
    how = ""
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append((current, how))
        if current.__cause__ is not None:
            current, how = current.__cause__, "cause"
        elif current.__context__ is not None and not current.__suppress_context__:
            current, how = current.__context__, "context"
        else:
            current = None

    # `how` is the way each one is chained to the newer one before it
    return [
        ErrorInfo(
            type=_type_name(exc),
            message=_message(exc),
            frames=get_frames(exc.__traceback__),
            chain=how,
        )
        for exc, how in reversed(chain)
    ]


def get_frames(tb: "TracebackType | None") -> list[Frame]:
    frames = []
    while tb is not None:
        frames.append(_frame(tb))
        tb = tb.tb_next
    if frames and not any(frame.is_app for frame in frames):
        # An error of Proper or of a library: all of its frames are shown
        for frame in frames:
            frame.is_app = True
            _add_details(frame)
    return frames


def format_text(errors: list[ErrorInfo], request: t.Any = None) -> str:
    """The plain text version of the debug page: what an agent reads, and
    what a human pastes to one."""
    error = errors[-1]
    out = [error.summary]
    if request is not None:
        out += ["", describe_request(request)]
        out += _text_params(request)
    where = error.where
    if where is not None:
        out += ["", f"At {where.path}:{where.lineno}, in {where.name}"]
        out += _text_context(where, indent="  ")
        out += _text_variables(where, indent="  ")

    for err in errors:
        out += ["", "Traceback (most recent call last):"]
        for group in err.groups():
            if isinstance(group, list):
                out.append(f"  ... {_count(len(group), 'frame')} of Proper or libraries ...")
                continue
            out.append(f"  {group.path}:{group.lineno}, in {group.name}")
            if group.line:
                out.append(f"    {group.line}")
        out.append(err.summary)
        if err.chain == "cause":
            out += ["", "The above exception was the direct cause of the following exception:"]
        elif err.chain == "context":
            out += ["", "During handling of the above exception, another exception occurred:"]
    return "\n".join(out) + "\n"


def describe_request(request: t.Any) -> str:
    """`POST /orders?ref=x -> OrderController.create`"""
    try:
        text = f"{request.method} {request.path}"
        if request.query_string:
            text += f"?{hide_url_passwords(request.query_string)}"
        route = request.matched_route
        to = getattr(route, "to", None) if route else None
        if to is not None:
            text += f" -> {getattr(to, '__qualname__', to)}"
        return text
    except Exception:
        return ""


# Private


def _type_name(exc: BaseException) -> str:
    cls = type(exc)
    module = cls.__module__
    if module in ("builtins", "__main__"):
        return cls.__qualname__
    return f"{module}.{cls.__qualname__}"


def _message(exc: BaseException) -> str:
    try:
        return hide_url_passwords(str(exc))
    except Exception:
        return MASK


def _is_app_path(filename: str) -> bool:
    if filename.startswith("<"):
        return False
    path = str(Path(filename).absolute())
    if path.startswith(PROPER_PATH):
        return False
    return not path.startswith(LIBRARY_PATHS)


def _display_path(filename: str) -> str:
    try:
        return str(Path(filename).absolute().relative_to(Path.cwd()))
    except ValueError:
        return filename


def _frame(tb: "TracebackType") -> Frame:
    code = tb.tb_frame.f_code
    filename = code.co_filename
    lineno = tb.tb_lineno or 0
    frame = Frame(
        path=_display_path(filename),
        lineno=lineno,
        name=code.co_name,
        line=linecache.getline(filename, lineno).strip(),
        is_app=_is_app_path(filename),
        filename=filename,
        tb_frame=tb.tb_frame,
    )
    if frame.is_app:
        _add_details(frame)
    return frame


def _add_details(frame: Frame) -> None:
    """The lines around the line of `frame`, and its variables."""
    lines = linecache.getlines(frame.filename)
    if lines:
        start = max(frame.lineno - CONTEXT_BEFORE, 1)
        end = min(frame.lineno + CONTEXT_AFTER, len(lines))
        frame.context = [(n, lines[n - 1].rstrip("\n")) for n in range(start, end + 1)]

    variables = dict(frame.tb_frame.f_locals) if frame.tb_frame else {}
    for name, value in variables.items():
        if name.startswith((".", "__")):
            continue
        if is_sensitive(name) and value:
            frame.variables[name] = MASK
        else:
            frame.variables[name] = safe_repr(value)


def _text_params(request: t.Any) -> list[str]:
    """The fields of the form, with the secret ones masked."""
    try:
        form = dict(request.form)
    except Exception:
        return []
    if not form:
        return []
    fields = {
        name: MASK if is_sensitive(name) and value else value
        for name, value in form.items()
    }
    return [f"Form data: {safe_repr(fields)}"]


def _text_context(frame: Frame, indent: str) -> list[str]:
    if not frame.context:
        return [f"{indent}  {frame.line}"] if frame.line else []
    width = len(str(frame.context[-1][0]))
    out = []
    for lineno, text in frame.context:
        mark = ">" if lineno == frame.lineno else " "
        out.append(f"{indent}{mark} {lineno:>{width}} | {text}".rstrip())
    return out


def _text_variables(frame: Frame, indent: str) -> list[str]:
    if not frame.variables:
        return []
    return ["", *(f"{indent}{name} = {value}" for name, value in frame.variables.items())]


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"
