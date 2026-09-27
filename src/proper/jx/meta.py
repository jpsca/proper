"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import ast
import builtins
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import (
    DuplicateDefDeclaration,
    InvalidArgument,
    InvalidImport,
    PathTraversalError,
)
from .lexer import (
    TAG_NAME_CHARS,
    TAG_NAME_START,
    WHITESPACE,
    scan_header,
    strip_inline_comments,
)
from .span import SourceMap


ALLOWED_NAMES_IN_EXPRESSION_VALUES = {
    "len": len,
    "max": max,
    "min": min,
    "pow": pow,
    "sum": sum,
    # Jinja allows using lowercase booleans, so we do it too for consistency
    "false": False,
    "true": True,
}


@dataclass(slots=True)
class ImportDecl:
    """One `{# import … #}` declaration, with offsets relative to the payload."""

    path: str
    name: str
    path_start: int
    path_end: int
    name_start: int
    name_end: int


@dataclass(slots=True)
class Meta:
    required: dict[str, type | None] = field(default_factory=dict)  # { attr: type or None }
    optional: dict[str, tuple[t.Any, type | None]] = field(default_factory=dict)  # { attr: (default, type or None) }
    imports: dict[str, str] = field(default_factory=dict)  # { component_name: relpath }
    css: tuple[str, ...] = ()
    js: tuple[str, ...] = ()


def extract_metadata(source: str, base_path: Path, fullpath: Path) -> Meta:
    """
    Extract metadata from the Jx template source.

    Arguments:
        source:
            The template source code.
        base_path:
            Absolute base path for all the template files, for relative imports.
        fullpath:
            The absolute full path of the current template, for relative imports.

    Returns:
        A `Meta` object containing the extracted metadata.

    """
    meta = Meta()
    def_found = False

    for keyword, expr, _offset, _expr_offset in scan_header(source):
        if keyword == "def":
            # Not run through `strip_inline_comments`: a `#` here is already a
            # Python comment, and `ast.parse` below knows what to do with it.
            if def_found:
                raise DuplicateDefDeclaration(str(fullpath))
            meta.required, meta.optional = parse_args_expr(expr)
            def_found = True
            continue

        expr = strip_inline_comments(expr).replace("\n", " ")

        if keyword == "import":
            decl = parse_import_expr(expr)
            import_path, import_name = decl.path, decl.name
            if import_path.startswith("."):
                if not fullpath.parts:
                    raise InvalidImport(
                        f"Relative import '{import_path}' not supported in string templates"
                    )
                resolved = (fullpath.parent / import_path).resolve()
                validate_import_path(import_path, resolved, base_path)
                import_path = resolved.relative_to(base_path).as_posix()
            meta.imports[import_name] = import_path

        elif keyword == "css":
            meta.css = (*meta.css, *parse_files_expr(expr))

        elif keyword == "js":
            meta.js = (*meta.js, *parse_files_expr(expr))

    return meta


def scan_import_lines(source: str) -> dict[str, int]:
    """
    Map each import's alias to the 1-based line its declaration is on.

    Keyed by the alias rather than the path, because `Meta.imports` has already
    resolved a relative path against the component's folder and the raw text
    would no longer match it.

    Only tooling needs this, so it is kept out of `Meta` and off the render
    path. It reads the same header `scan_header` reads, so a declaration the
    renderer ignores is ignored here too.

    Returns:
        `{import_name: line}`. An unparseable declaration is skipped; the
        caller is reporting on a file it already knows may be broken.

    """
    lines: dict[str, int] = {}
    source_map = SourceMap(source)

    for keyword, expr, offset, _expr_offset in scan_header(source):
        if keyword != "import":
            continue
        expr = strip_inline_comments(expr).replace("\n", " ")
        try:
            decl = parse_import_expr(expr)
        except InvalidImport:
            continue
        lines.setdefault(decl.name, source_map.locate(offset)[0])

    return lines


def annotation_to_type(annotation: ast.expr | None) -> type | None:
    """
    Convert an AST annotation node to a Python type.
    Returns None if the annotation is not a supported builtin type.

    ::: note
    For generic types like `list[str]` or `dict[str, int]`, only the base
    type (`list`, `dict`) is extracted. The generic parameters are discarded.
    This is sufficient for basic `isinstance()` validation but won't validate
    element types.

    To preserve full generic type info in the future, we could use
    `eval(ast.unparse(annotation), {"__builtins__": {}}, vars(builtins))`
    which returns the actual generic type object, which can be used with more
    advanced type checking libraries like `typeguard` or manual element validation.
    :::
    """
    if annotation is None:
        return None

    # For generics like `list[str]`, extract the base type
    if isinstance(annotation, ast.Subscript):
        annotation = annotation.value

    if isinstance(annotation, ast.Name):
        result = getattr(builtins, annotation.id, None)
        return result if isinstance(result, type) else None

    return None


def parse_args_expr(expr: str) -> tuple[dict[str, type | None], dict[str, tuple[t.Any, type | None]]]:
    expr = expr.strip(" *,/")
    required: dict[str, type | None] = {}
    optional: dict[str, tuple[t.Any, type | None]] = {}

    try:
        p = ast.parse(f"def component(*,\n{expr}\n): pass")
    except SyntaxError as err:
        raise InvalidArgument(err) from err

    args = p.body[0].args  # type: ignore
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):  # noqa: B905
        arg_type = annotation_to_type(arg.annotation)
        if default is None:
            required[arg.arg] = arg_type
            continue
        default_expr = ast.unparse(default)
        optional[arg.arg] = (eval_expression(default_expr), arg_type)

    return required, optional


def eval_expression(input_string: str) -> t.Any:
    code = compile(input_string, "<string>", "eval")
    for name in code.co_names:
        if name not in ALLOWED_NAMES_IN_EXPRESSION_VALUES:
            raise InvalidArgument(f"Use of {name} not allowed")
    return eval(code, {"__builtins__": {}}, ALLOWED_NAMES_IN_EXPRESSION_VALUES)


def parse_files_expr(expr: str) -> list[str]:
    files = []
    for part in expr.split(","):
        url = part.strip().strip("\"'").rstrip("/")
        if url:
            files.append(url)
    return files


def parse_import_expr(expr: str) -> ImportDecl:
    """
    Read a `"path/to/component.jx" as TagName` declaration.

    The offsets of both halves are reported along with their text. They are
    known here anyway, and an editor needs them to make the path and the alias
    separately clickable.
    """
    if expr[:1] != '"':
        raise InvalidImport(expr)
    close = expr.find('"', 1)
    if close < 2:  # an empty path is not a path
        raise InvalidImport(expr)
    path = expr[1:close]

    rest = expr[close + 1:]
    end = len(rest)
    # Where `rest` begins, so the name offsets can be reported against `expr`.
    base = close + 1

    i = 0
    while i < end and rest[i] in WHITESPACE:
        i += 1
    if i == 0 or rest[i : i + 2] != "as":
        raise InvalidImport(expr)

    i += 2
    start = i
    while i < end and rest[i] in WHITESPACE:
        i += 1
    if i == start:
        raise InvalidImport(expr)

    if i >= end or rest[i] not in TAG_NAME_START:
        raise InvalidImport(expr)
    start = i
    i += 1
    while i < end and rest[i] in TAG_NAME_CHARS:
        i += 1

    return ImportDecl(
        path=path,
        name=rest[start:i],
        path_start=1,
        path_end=close,
        name_start=base + start,
        name_end=base + i,
    )


def validate_import_path(path: str, resolved: Path, base_path: Path) -> None:
    """
    Validate that the resolved import path does not escape the component root.

    Arguments:
        path:
            The original import path string (for error messages).
        resolved:
            The resolved absolute path of the import.
        base_path:
            The base path that all imports must stay within.

    Raises:
        PathTraversalError: If the resolved path escapes the base path.

    """
    if not resolved.is_relative_to(base_path):
        raise PathTraversalError(path)
