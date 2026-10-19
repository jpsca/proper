"""
Fallback error handlers
"""

import sys
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from hecto import JinjaRender
from markupsafe import Markup

from ..constants import GET
from ..helpers import jsonplus, logger
from .debug_info import (
    describe_request,
    format_text,
    get_errors,
    hide_url_passwords,
    is_sensitive,
)


if TYPE_CHECKING:
    from typing import Any


TEMPLATES = (Path(__file__).parent / "templates").absolute()
jinja_render = JinjaRender(TEMPLATES)
# The pages show the request, the error and the variables of the app
jinja_render.env.autoescape = True


def _include_raw(name):
    return Markup(jinja_render.loader.get_source(jinja_render.env, name)[0])


jinja_render.globals["include_raw"] = _include_raw


def render(template: str, **data) -> str:
    if not data:
        return (TEMPLATES / template).read_text()
    try:
        return jinja_render(template, **data)
    except Exception:
        logger.exception("")
        return render("fallback-error.html")


def debug_not_found_handler(app, request, response) -> None:
    if is_index(request):
        return render_default_index(request, response)

    error = response.error
    wants = wanted_format(request)
    if wants != "html":
        text = format_not_found_text(error, request, app.routes)
        return set_text_body(response, wants, text, type(error).__name__, str(error))

    data = {
        "config": redact_sensitive_info(app.config),
        "response": response,
        "title": type(error).__name__,
        "description": str(error),
        "request_line": describe_request(request),
        "routes": app.routes,
    }
    data.update(get_request_data(request))
    response.body = render("debug-not-found.jx", **data)


def wanted_format(request) -> str:
    """`"html"`, `"json"`, or `"text"`: what the client asked for first in
    its `accept` header. A browser asks for HTML; an agent or a tool like
    `curl`, which asks for anything (`*/*`), gets plain text."""
    try:
        accept = request.accept
    except Exception:
        accept = []
    for media in accept:
        if media in ("text/html", "application/xhtml+xml"):
            return "html"
        if media == "application/json" or media.endswith("+json"):
            return "json"
    return "text"


def set_text_body(response, wants: str, text: str, error_type: str, message: str) -> None:
    if wants == "json":
        response.content_type = "application/json"
        response.body = jsonplus.dumps({"error": error_type, "message": message, "details": text})
    else:
        response.content_type = "text/plain"
        response.body = text


def format_not_found_text(error, request, routes) -> str:
    out = [f"{type(error).__name__}: {error}", ""]
    out.append("Routes, in the order they are matched:")
    rows = []
    for route in routes:
        if route.build_only:
            continue
        to = route.to.__qualname__ if route.to else (route.redirect and f"-> {route.redirect}") or ""
        rows.append((route.method or "-", route.path, route.name or "", to))
    widths = [max((len(row[i]) for row in rows), default=0) for i in range(3)]
    for row in rows:
        out.append("  " + "  ".join(col.ljust(widths[i]) for i, col in enumerate(row[:3])) + "  " + row[3])
    return "\n".join(line.rstrip() for line in out) + "\n"


MASK = "▒" * 4

#: Dicts, lists and tuples deeper than this are shown as `MASK`.
MAX_REDACT_DEPTH = 32

#: After this many values, the rest are shown as `MASK`.
MAX_REDACT_VALUES = 10_000


def redact_sensitive_info(data: dict) -> dict:
    """A copy of `data` for the debug pages, with the value of every key
    that holds a secret (`is_sensitive()`: one that ends with `PASSWORD`,
    `SECRET_KEYS`, `TOKEN`, `API_KEY`, `COOKIE`, `AUTHORIZATION`, etc., in
    any letter case) redacted, in `data` and in every dict, list, tuple or
    named tuple inside it, at any depth. The password of a URL in any
    other string, like `postgres://user:password@host/db`, is masked.

    Under such a key, every value at any depth is replaced by
    `redact_value(value)`, except an empty or false one (`""`, `None`, `0`,
    `False`), which is kept. Other values are kept as they are.

    The copy is made of plain containers: a dict (or dict subclass) becomes
    a `dict`, a named tuple a `dict` of its fields (so its field names
    follow the key rules), any other tuple a `tuple`, and a list a `list`.
    These are shown as `MASK` (`▒▒▒▒`) instead:

    - a container that is already on the path from `data` to it (a cycle);
    - a container more than `MAX_REDACT_DEPTH` (32) levels deep;
    - every value after the first `MAX_REDACT_VALUES` (10 000);
    - a value or key that raises when it is read or compared.

    So it never raises, and it reads at most `MAX_REDACT_VALUES` values.
    """
    budget = [MAX_REDACT_VALUES]
    result = _redact(data, False, frozenset(), 0, budget)
    return result if isinstance(result, dict) else {}




def _redact(
    value: "Any", secret: bool, path: frozenset, depth: int, budget: list
) -> "Any":
    """`value` copied by the rules of `redact_sensitive_info`; `secret` is
    true under a sensitive key, `path` holds the `id()` of the containers
    above `value`, and `budget[0]` is the number of values left to read."""
    budget[0] -= 1
    if budget[0] < 0:
        return MASK
    try:
        if isinstance(value, tuple) and hasattr(value, "_asdict"):
            value_id = id(value)
            value = dict(value._asdict())
        elif isinstance(value, dict | list | tuple):
            value_id = id(value)
        else:
            if secret and value:
                return redact_value(value)
            if isinstance(value, str):
                return hide_url_passwords(value)
            return value

        if value_id in path or depth >= MAX_REDACT_DEPTH:
            return MASK
        path = path | {value_id}
        depth += 1

        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                try:
                    item_secret = secret or is_sensitive(key)
                except Exception:
                    result[key] = MASK
                    continue
                result[key] = _redact(item, item_secret, path, depth, budget)
            return result
        items = [_redact(item, secret, path, depth, budget) for item in value]
        return items if isinstance(value, list) else tuple(items)
    except Exception:
        return MASK


def redact_value(val: "Any") -> str:
    """The text of `val` with each character after the fourth replaced by
    `▒`. A value that is not a string is redacted as its `str()`, so
    `12345678` becomes `1234▒▒▒▒`; one whose `str()` raises becomes
    `▒▒▒▒`."""
    if isinstance(val, str):
        text = val
    else:
        try:
            text = str(val)
        except Exception:
            return MASK
    return f"{text[:4]}{'▒' * (len(text) - 4)}"


def is_index(request) -> bool:
    return request.method == GET and request.path == "/"


def render_default_index(request, response) -> None:
    data = {
        "proper_version": version("proper"),
        "server_software": request.server_software,
        "python_version": sys.version,
    }
    response.body = render("default-index.jx", **data)


def debug_error_handler(app, request, response) -> None:
    error = response.error
    logger.exception(error)
    errors = get_errors(error)
    text = format_text(errors, request)
    wants = wanted_format(request)
    if wants != "html":
        return set_text_body(response, wants, text, errors[-1].type, errors[-1].message)

    data = {
        "config": redact_sensitive_info(app.config),
        "request": request,
        "response": response,
        "title": errors[-1].type,
        "description": errors[-1].message,
        "request_line": describe_request(request),
        "errors": errors,
        "text": text,
    }
    data.update(get_request_data(request))
    response.body = render("debug-error.jx", **data)


def get_request_data(request) -> dict:
    try:
        request_query = request.query
    except Exception:
        request_query = None
    try:
        request_form = request.form
    except Exception:
        request_form = None
    try:
        request_headers = dict(request.headers)
    except Exception:
        request_headers = None
    return {
        "request_query": _redact_or_none(request_query),
        "request_form": _redact_or_none(request_form),
        "request_headers": _redact_or_none(request_headers),
    }


def _redact_or_none(data: "Any") -> "dict | None":
    return None if data is None else redact_sensitive_info(dict(data))


def fallback_not_found_handler(response) -> None:
    response.body = render("fallback-not-found.html")


def fallback_forbidden_handler(response) -> None:
    response.body = render("fallback-forbidden.html")


def fallback_error_handler(response) -> None:
    logger.exception(response.error)
    response.body = render("fallback-error.html")
