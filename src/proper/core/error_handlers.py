"""
Fallback error handlers
"""

import sys
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

import inflection
import traceback_with_variables as traceback2
from hecto import JinjaRender
from markupsafe import Markup

from ..constants import GET
from ..helpers import logger


if TYPE_CHECKING:
    from typing import Any


TEMPLATES = (Path(__file__).parent / "templates").absolute()
jinja_render = JinjaRender(TEMPLATES)


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
    data = {
        "config": redact_sensitive_info(app.config),
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "routes": app.routes,
    }
    data.update(get_request_data(request))
    response.body = render("debug-not-found.jx", **data)


MASK = "▒" * 4

#: Dicts, lists and tuples deeper than this are shown as `MASK`.
MAX_REDACT_DEPTH = 32

#: After this many values, the rest are shown as `MASK`.
MAX_REDACT_VALUES = 10_000


def redact_sensitive_info(data: dict) -> dict:
    """A copy of `data` for the debug pages, with the value of every
    `SECRET_KEYS` key and every `password` key (in any letter case)
    redacted, in `data` and in every dict, list, tuple or named tuple
    inside it, at any depth.

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


def _is_sensitive(key: "Any") -> bool:
    return key == "SECRET_KEYS" or (isinstance(key, str) and key.lower() == "password")


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
            return value

        if value_id in path or depth >= MAX_REDACT_DEPTH:
            return MASK
        path = path | {value_id}
        depth += 1

        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                try:
                    item_secret = secret or _is_sensitive(key)
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
    excp = traceback2.format_exc()
    data = {
        "config": redact_sensitive_info(app.config),
        "request": request,
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "traceback": str(excp),
    }
    data.update(get_request_data(request))
    response.body = render("debug-error.jx", **data)


def get_title(error: "Any") -> str:
    return inflection.titleize(error.__class__.__name__)


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
        "request_query": request_query,
        "request_form": request_form,
        "request_headers": request_headers,
    }


def fallback_not_found_handler(response) -> None:
    response.body = render("fallback-not-found.html")


def fallback_forbidden_handler(response) -> None:
    response.body = render("fallback-forbidden.html")


def fallback_error_handler(response) -> None:
    logger.exception(response.error)
    response.body = render("fallback-error.html")
