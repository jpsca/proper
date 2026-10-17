import inspect
import os
import re
import types
import typing as t
from dataclasses import dataclass
from pathlib import Path


__all__ = ("ERROR", "WARNING", "Problem", "handler_class", "of_app", "relpath", "subclasses", "where", "where_attr")

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Problem:
    """Something `proper check` found: an `error` (it will fail, or lose
    data) or a `warning` (probably a mistake). `path` and `line` say where,
    when known."""

    level: str
    message: str
    path: str = ""
    line: int = 0
    col: int = 0

    def __str__(self) -> str:
        where = self.path
        if where and self.line:
            where += f":{self.line}"
            if self.col:
                where += f":{self.col}"
        prefix = f"{where}: " if where else ""
        return f"{prefix}{self.level}: {self.message}"


def relpath(path: str | os.PathLike) -> str:
    """`path` relative to the current folder, when it is inside it."""
    path = Path(path)
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def where(obj: t.Any) -> dict[str, t.Any]:
    """The file and line where a class or function is defined, as the
    keyword arguments of a `Problem`; empty when the source is unknown."""
    try:
        _, line = inspect.getsourcelines(obj)
        path = inspect.getsourcefile(obj) or inspect.getfile(obj)
    except (TypeError, OSError):
        return {}
    return {"path": relpath(path), "line": line}


def where_attr(cls: type, name: str) -> dict[str, t.Any]:
    """The line where the class `cls` assigns `name`, or where the class
    starts when it doesn't."""
    loc = where(cls)
    if not loc:
        return loc
    lines, start = inspect.getsourcelines(cls)
    rx = re.compile(rf"^\s*{re.escape(name)}\s*[:=]")
    for i, text in enumerate(lines):
        if rx.match(text):
            return {**loc, "line": start + i}
    return loc


def subclasses[T](cls: type[T]) -> list[type[T]]:
    """The subclasses of `cls` at any depth."""
    found: list[type[T]] = []
    pending = [cls]
    while pending:
        for sub in pending.pop(0).__subclasses__():
            if sub not in found:
                found.append(sub)
                pending.append(sub)
    return found


def handler_class(handler: types.FunctionType) -> type | None:
    """The class of a method, from its globals (its `__qualname__` names
    it), or `None` when the class is not at the top of its module."""
    cls_name, _, _ = handler.__qualname__.rpartition(".")
    cls = handler.__globals__.get(cls_name)
    return cls if isinstance(cls, type) else None


def of_app(app: t.Any, cls: type) -> bool:
    """Whether `cls` is defined in the package of the app."""
    module = cls.__module__
    return module == app.name or module.startswith(f"{app.name}.")
