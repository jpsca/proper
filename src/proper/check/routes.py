import re
import typing as t

from ..compile import compile_views, plan_for
from ..compile.dispatch import LoweringError, validate
from ..helpers.imports import import_string
from ..views import CompileError
from .problem import ERROR, WARNING, Problem, relpath, where


if t.TYPE_CHECKING:
    from ..app import App


__all__ = ("check_controllers", "check_routes", "check_views")

# A line of the views compiler: `path:line:col: message`
RX_COMPILER_LINE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<message>.*)$")


def check_controllers(app: "App") -> list[Problem]:
    """Every routed action and error handler can be dispatched: its
    controller imports, and its `before`/`after` callbacks exist."""
    problems = []
    actions: dict[tuple[type, str], None] = {}
    for route in app.routes:
        if route.to is None:
            continue
        try:
            actions[route.resolve()] = None
        except (ImportError, AttributeError) as err:
            problems.append(Problem(
                ERROR,
                f"the controller of the route {_describe(route)} can't be "
                f"loaded ({err}); a controller must be a class at the top "
                f"of its module",
                **where(route.to),
            ))
    for handler in app.router.error_handlers.values():
        cls_name, action = handler.__qualname__.rsplit(".", 1)
        actions[(getattr(import_string(handler.__module__), cls_name), action)] = None
    for cls, action in actions:
        try:
            validate(plan_for(cls, action))
        except LoweringError as err:
            problems.append(Problem(ERROR, str(err), **where(cls)))
    return problems


def check_views(app: "App") -> list[Problem]:
    """Every view compiles. They are written where the app reads them, as
    `proper jx compile` does."""
    if not app.catalog.compiler:
        return [Problem(WARNING, "the views were not checked: there is no views compiler for this platform")]
    try:
        compile_views(app, force=True)
    except CompileError as err:
        return compiler_problems(str(err))
    return []


def compiler_problems(output: str) -> list[Problem]:
    """The errors that the views compiler printed, one per line."""
    problems = []
    for text in output.splitlines():
        if not text.strip():
            continue
        match = RX_COMPILER_LINE.match(text)
        if match:
            problems.append(Problem(
                ERROR,
                match["message"],
                path=relpath(match["path"]),
                line=int(match["line"]),
                col=int(match["col"]),
            ))
        else:
            problems.append(Problem(ERROR, text))
    return problems


def check_routes(app: "App") -> list[Problem]:
    """No route is hidden by an earlier one with the same method, path and
    host, and a name isn't given to routes with different paths (`url_for`
    uses the first)."""
    problems = []
    by_match: dict[tuple, t.Any] = {}
    by_name: dict[str, t.Any] = {}
    for route in app.routes:
        loc = where(route.to) if route.to else {}
        if not route.build_only:
            key = (route.method, route.path, route.host)
            first = by_match.setdefault(key, route)
            if first is not route:
                problems.append(Problem(
                    ERROR,
                    f"the route {_describe(route)} never matches: "
                    f"an earlier route has the same method, path and host"
                    f"{_named(first)}",
                    **loc,
                ))
        if route.name:
            first = by_name.setdefault(route.name, route)
            if first is not route and (first.path, first.host) != (route.path, route.host):
                problems.append(Problem(
                    ERROR,
                    f"the name `{route.name}` is also used by the route "
                    f"{_describe(first)}; `url_for` builds that one",
                    **loc,
                ))
    return problems


def _describe(route: t.Any) -> str:
    host = f" (host {route.host})" if route.host else ""
    return f"{route.method} {route.path}{host}"


def _named(route: t.Any) -> str:
    return f" (`{route.name}`)" if route.name else ""
