import ast
import difflib
import typing as t
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..views.debug import _find_entry
from .problem import ERROR, Problem, relpath


if t.TYPE_CHECKING:
    from ..app import App


__all__ = ("check_code_urls", "check_view_urls", "url_problem")

# The calls that take the name of a route as their first argument
URL_CALLS = ("url_for", "redirect_to")
# How alike a name must be to a route name to be suggested
NAME_CUTOFF = 0.75


@dataclass(frozen=True)
class UrlCall:
    """A call of `url_for` (or `redirect_to`) with a literal route name."""

    name: str
    keywords: frozenset[str]
    # An object to take the placeholders from, or `**kwargs`: the
    # placeholders it may fill are unknown
    open: bool
    line: int
    col: int
    # The first line of the function that makes the call
    first_line: int = 1


def url_problem(app: "App", call: UrlCall) -> str:
    """What is wrong with a call that builds the URL of a route, or `""`:
    a route that doesn't exist, or a placeholder of its path not given and
    without a default."""
    name = call.name.removesuffix("Controller")
    routes = app.router._routes_by_name
    route = routes.get(name)
    if route is None:
        match = difflib.get_close_matches(name, list(routes), n=1, cutoff=NAME_CUTOFF)
        hint = f" (did you mean `{match[0]}`?)" if match else ""
        return f"there is no route named `{call.name}`{hint}"
    if call.open:
        return ""
    missing = [
        key for key in route.path_placeholders
        if key not in call.keywords and key not in route.url_defaults
    ]
    if missing:
        names = ", ".join(f"`{key}`" for key in missing)
        return f"the route `{name}` ({route.path}) needs {names}"
    return ""


def check_view_urls(app: "App") -> list[Problem]:
    """The route names given to `url_for` in the views, read from the
    compiled views (so this runs after they compile)."""
    output = app.catalog.output
    if output is None or not output.is_dir():
        return []
    problems: dict[tuple, Problem] = {}
    templates: dict[Path, list[str]] = {}
    for path in sorted(output.rglob("*.py")):
        tree = ast.parse(path.read_bytes(), str(path))
        tables = _tables(tree)
        if "LINEMAP" not in tables or "SOURCES" not in tables:
            continue
        sources = [(path.parent / source).resolve() for source in tables["SOURCES"]]
        if not all(source.exists() for source in sources):
            # Left from a view that was deleted
            continue
        module = {"LINEMAP": tables["LINEMAP"]}
        lines = path.read_text().splitlines()
        for call in _view_calls(tree, lines):
            message = url_problem(app, call)
            if not message:
                continue
            entry = _find_entry(module, call.line, call.col, call.first_line)
            if entry is None:
                problem = Problem(ERROR, message, path=relpath(path), line=call.line)
            else:
                source = sources[entry[3]]
                if source not in templates:
                    templates[source] = source.read_text().splitlines()
                # The compiler counts the columns of the template in UTF-8 bytes
                text = templates[source][entry[4] - 1]
                col = len(text.encode()[: entry[5]].decode(errors="ignore"))
                problem = Problem(
                    ERROR, message, path=relpath(source), line=entry[4], col=col + 1
                )
            # A component is compiled into every view that imports it
            problems.setdefault((problem.path, problem.line, problem.col, message), problem)
    return sorted(problems.values(), key=_position)


def _position(problem: Problem) -> tuple[str, int, int]:
    return (problem.path, problem.line, problem.col)


def _tables(tree: ast.Module) -> dict[str, t.Any]:
    """The literal tables a compiled view declares, by name."""
    tables = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in ("LINEMAP", "SOURCES"):
                tables[target.id] = ast.literal_eval(node.value)
    return tables


def _view_calls(tree: ast.Module, lines: list[str]) -> list[UrlCall]:
    """The calls of the `url_for` global with a literal name, in compiled
    code: `_globals['url_for'](...)`, or `_pure(_P, site, url_for, names,
    *values)` when an argument isn't constant."""
    calls = []
    for function, node in _calls(tree):
        first_line = function.lineno if function else 1
        col = _char_col(lines, node)
        if _is_global_url_for(node.func):
            keywords = [kw.arg for kw in node.keywords]
            call = _literal_call(node.args, keywords, node.lineno, col, first_line)
        elif (
            isinstance(node.func, ast.Name)
            and node.func.id == "_pure"
            and len(node.args) >= 4
            and _is_global_url_for(node.args[2])
            and isinstance(node.args[3], ast.Tuple)
        ):
            names: list[str | None] = [
                elt.value for elt in node.args[3].elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]
            values = node.args[4:]
            positional = values[: len(values) - len(names)]
            call = _literal_call(positional, names, node.lineno, col, first_line)
        else:
            continue
        if call:
            calls.append(call)
    return calls


def _is_global_url_for(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "_globals"
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "url_for"
    )


def _calls(tree: ast.AST) -> t.Iterator[tuple[ast.FunctionDef | None, ast.Call]]:
    """Every call in `tree`, with the outermost function that makes it."""
    pending: list[tuple[ast.AST, ast.FunctionDef | None]] = [(tree, None)]
    while pending:
        node, function = pending.pop()
        for child in ast.iter_child_nodes(node):
            owner = function
            if owner is None and isinstance(child, ast.FunctionDef):
                owner = child
            if isinstance(child, ast.Call):
                yield owner, child
            pending.append((child, owner))


def _char_col(lines: list[str], node: ast.expr) -> int:
    """The column of `node` in characters: `ast` counts UTF-8 bytes."""
    line = lines[node.lineno - 1]
    return len(line.encode()[: node.col_offset].decode(errors="ignore"))


def _literal_call(
    args: list[ast.expr],
    keywords: list[str | None],
    line: int,
    col: int,
    first_line: int = 1,
) -> UrlCall | None:
    """The call, when its first argument is the literal name of a route
    (not a path, nor a full URL)."""
    if not args or not isinstance(args[0], ast.Constant) or not isinstance(args[0].value, str):
        return None
    name = args[0].value
    if name.startswith(("/", "http")):
        return None
    names = frozenset(kw for kw in keywords if kw)
    # `None` is a `**kwargs`
    spread = None in keywords
    has_object = len(args) > 1 or "object" in names or "obj" in names
    return UrlCall(
        name=name,
        keywords=names,
        open=spread or has_object,
        line=line,
        col=col,
        first_line=first_line,
    )


def check_code_urls(app: "App") -> list[Problem]:
    """The route names given to `url_for` and `redirect_to` in the Python
    code of the app."""
    output = app.catalog.output
    paths = [
        path
        for path in sorted(app.root_path.rglob("*.py"))
        if "__pycache__" not in path.parts
        and not (output is not None and path.is_relative_to(output))
    ]
    with ThreadPoolExecutor() as pool:
        found = pool.map(_code_calls, paths)
    problems = []
    for path, calls in zip(paths, found, strict=True):
        for call in calls:
            message = url_problem(app, call)
            if message:
                problems.append(Problem(
                    ERROR, message, path=relpath(path), line=call.line, col=call.col + 1
                ))
    return sorted(problems, key=_position)


def _code_calls(path: Path) -> list[UrlCall]:
    """The calls of `url_for` or `redirect_to` with a literal name in a
    module, as a function (`url_for(...)`) or a method (`app.url_for(...)`,
    `self.redirect_to(...)`). A module that doesn't parse has none: Python
    reports it when the app is imported."""
    try:
        source = path.read_text()
        tree = ast.parse(source, str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    lines = source.splitlines()
    calls = []
    for _, node in _calls(tree):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else ""
        )
        if name not in URL_CALLS:
            continue
        keywords = [kw.arg for kw in node.keywords]
        call = _literal_call(node.args, keywords, node.lineno, _char_col(lines, node))
        if call:
            calls.append(call)
    return calls
