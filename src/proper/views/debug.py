"""
minijx runtime: tracebacks that point to the templates.

A compiled component is Python code, so an error while rendering it would
show lines of that code. Each module has a `LINEMAP`: for its lines (and, in
a line that renders several `{{ }}`, for the columns of each one) the
template, line and columns they come from:

    (module line, first column or -1 for the whole line, end column,
     index in SOURCES, template line, first column, end column or -1)

When a render fails, the catalog rewrites the traceback, as Jinja does: each
frame of a compiled module is replaced by a frame "in" the template, at its
line, with the template's variables as its locals. Python then shows the
`.jx` line, with `^^^` under the expression that failed. The frames of
minijx itself are dropped, unless there is no template frame to show.

Two messages are made clearer: a name that is neither an argument nor a
global (a `KeyError` of `_globals`) and a component called without a
required argument (a `TypeError` naming its Python function).

Nothing of this runs unless a render raises.
"""

import os
import re
import types
import typing as t


__all__ = ["rewrite_traceback"]

_PACKAGE = os.path.dirname(os.path.abspath(__file__)) + os.sep

# Python functions that are not the component itself: their name in the
# traceback. Macros keep their own.
_NESTED = (
    (re.compile(r"_fill\d+$"), "fill"),
    (re.compile(r"_tag\d+$"), "tag"),
    (re.compile(r"_r\d+$"), "loop"),
)


def rewrite_traceback(exc: BaseException) -> BaseException:
    """
    Replace, in the traceback of `exc`, the frames of compiled components
    with frames in their templates. Returns `exc`, with the new traceback.
    """
    frames: list[types.TracebackType] = []
    internal: list[bool] = []
    found = False
    tb = exc.__traceback__
    while tb is not None:
        module = tb.tb_frame.f_globals
        fake = None
        if "LINEMAP" in module and "MINIJX_FORMAT" in module:
            fake = _template_frame(exc, tb, module)
        if fake is not None:
            found = True
            frames.append(fake)
            internal.append(False)
        else:
            frames.append(tb)
            internal.append(tb.tb_frame.f_code.co_filename.startswith(_PACKAGE))
        tb = tb.tb_next

    last = _last_template_frame(exc)
    if last is not None:
        _explain(exc, *last)

    if found:
        frames = [f for f, hide in zip(frames, internal, strict=True) if not hide]
    tb_next = None
    for tb in reversed(frames):
        tb.tb_next = tb_next
        tb_next = tb
    return exc.with_traceback(tb_next)


def _template_frame(
    exc: BaseException,
    tb: types.TracebackType,
    module: dict[str, t.Any],
) -> "types.TracebackType | None":
    frame = tb.tb_frame
    code = frame.f_code
    col = None
    if tb.tb_lasti >= 0:
        positions = list(code.co_positions())
        index = tb.tb_lasti // 2
        if index < len(positions):
            col = positions[index][2]
    entry = _find_entry(module, tb.tb_lineno, col, code.co_firstlineno)
    if entry is None:
        return None
    _, _, _, source, line, first, end = entry
    try:
        relpath = module["SOURCES"][source]
    except (KeyError, IndexError):
        return None
    path = os.path.normpath(os.path.join(os.path.dirname(code.co_filename), relpath))

    name = code.co_name
    for pattern, label in _NESTED:
        if pattern.match(name):
            name = label
            break
    else:
        if name.startswith("_c_"):
            name = "template"
    variables = {k: v for k, v in frame.f_locals.items() if not k.startswith("_")}
    return _fake_traceback(exc, path, line, first, end, name, variables)


def _last_template_frame(exc: BaseException):
    """The innermost frame of a compiled module, with its module."""
    found = None
    tb = exc.__traceback__
    while tb is not None:
        module = tb.tb_frame.f_globals
        if "LINEMAP" in module and "MINIJX_FORMAT" in module:
            found = (tb.tb_frame, module)
        tb = tb.tb_next
    return found


_MISSING_ARG = re.compile(r"^(_c_\w+)\(\)")


def _explain(exc: BaseException, frame: types.FrameType, module: dict[str, t.Any]) -> None:
    components = module.get("COMPONENTS", {})
    if isinstance(exc, KeyError) and len(exc.args) == 1 and isinstance(exc.args[0], str):
        name = exc.args[0]
        glob = frame.f_locals.get("_globals")
        if isinstance(glob, dict) and name not in glob:
            where = components.get(frame.f_code.co_name) or _component_at(frame, module)
            exc.add_note(
                f"`{name}` is not defined: it is not an argument"
                + (f" of {where}" if where else "")
                + ", a variable set in it, nor a global of the catalog"
            )
    elif isinstance(exc, TypeError) and exc.args and isinstance(exc.args[0], str):
        m = _MISSING_ARG.match(exc.args[0])
        if m and m[1] in components:
            exc.args = (f"<{components[m[1]]}>" + exc.args[0][m.end():], *exc.args[1:])


def _component_at(frame: types.FrameType, module: dict[str, t.Any]) -> "str | None":
    """The component a line of a module comes from, for nested functions
    (fills, tags, loops, macros): COMPONENTS is in the order of SOURCES."""
    entry = _find_entry(module, frame.f_lineno, None, frame.f_code.co_firstlineno)
    names = list(module.get("COMPONENTS", {}).values())
    if entry is not None and entry[3] < len(names):
        return names[entry[3]]
    return None


def _find_entry(module: dict[str, t.Any], lineno: int, col: "int | None", first_line: int):
    """The LINEMAP entry for a module line and, if known, the column of the
    instruction that failed. A line with no entry takes the closest one
    above it in the same function."""
    index = module.get("__minijx_lineindex__")
    if index is None:
        index = {}
        for entry in module["LINEMAP"]:
            index.setdefault(entry[0], []).append(entry)
        module["__minijx_lineindex__"] = index
    for number in range(lineno, first_line - 1, -1):
        entries = index.get(number)
        if not entries:
            continue
        if number == lineno and col is not None:
            for entry in entries:
                if entry[1] >= 0 and entry[1] <= col < entry[2]:
                    return entry
        for entry in entries:
            if entry[1] < 0:
                return entry
        return entries[0]
    return None


class _Raiser(dict):
    """The locals of a fake frame: the template's variables, and any other
    name raises the exception."""

    def __init__(self, exc: BaseException, variables: dict[str, t.Any]) -> None:
        super().__init__(variables)
        self.exc = exc

    def __missing__(self, key: str) -> t.NoReturn:
        raise self.exc


def _fake_traceback(
    exc: BaseException,
    path: str,
    line: int,
    first: int,
    end: int,
    name: str,
    variables: dict[str, t.Any],
) -> "types.TracebackType | None":
    """
    A traceback entry in `path` at `line`, made by running code compiled
    with that file name, whose only instruction, at that line and at the
    column of the expression, raises `exc`: a name made of underscores as
    wide as the expression. Python shows carets under it, in the real line.
    Without the expression's columns, the name covers the whole line, and
    Python shows no carets.
    """
    if end < 0 or end <= first:
        first, end = _whole_line(path, line)
    width = max(end - first, 1)
    placeholder = "_" * width
    if first == 0:
        text = placeholder
    else:
        text = "(" + " " * (first - 1) + placeholder + ")"
    source = "\n" * (line - 1) + text
    try:
        code = compile(source, path, "exec")
    except SyntaxError:  # pragma: no cover
        return None
    code = code.replace(co_name=name, co_qualname=name)
    try:
        exec(code, {"__name__": path, "__file__": path}, _Raiser(exc, variables))
    except BaseException as err:
        fake = err.__traceback__
        # [this function's frame] -> [the fake frame] -> [__missing__]
        if fake is not None and fake.tb_next is not None:
            return fake.tb_next
    return None  # pragma: no cover


def _whole_line(path: str, line: int) -> tuple[int, int]:
    """The byte columns of the text of a line, without its indentation."""
    import linecache

    text = linecache.getline(path, line).rstrip("\r\n").encode("utf-8")
    stripped = text.lstrip()
    first = len(text) - len(stripped)
    return first, len(text.rstrip()) if stripped else first + 1
