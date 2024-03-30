"""
Fallback error handlers

"""

import sys
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

import inflection
import traceback_with_variables as traceback2
from markupsafe import Markup

from proper.constants import GET
from proper.helpers import Render, logger


if TYPE_CHECKING:
    from typing import Any


TEMPLATES = (Path(__file__).parent / "templates").absolute()
jinja_render = Render(TEMPLATES)


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
        "config": deepsort_dict(redact_sensible_info(app.config)),
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "routes": app.routes,
    }
    data.update(get_request_data(request))
    response.body = render("debug-not-found.jinja", **data)


def redact_sensible_info(data: dict) -> dict:
    if "SECRET_KEYS" in data:
        data["SECRET_KEYS"] = [redact_value(key) for key in data["SECRET_KEYS"]]

    redacted_data = {}
    for name, value in data.items():
        if isinstance(value, dict):
            value = redact_sensible_info(value)
        elif name.lower() == "password" and value:
            value = redact_value(value)
        redacted_data[name] = value

    return redacted_data


def redact_value(val: str) -> str:
    return f"{val[:4]}{'▒' * (len(val) - 4)}"


def is_index(request) -> bool:
    return request.method == GET and request.path == "/"


def render_default_index(request, response) -> None:
    data = {
        "proper_version": version("proper"),
        "server_software": request.env.get("server_software", ""),
        "python_version": sys.version,
    }
    response.body = render("default-index.jinja", **data)


def debug_error_handler(app, request, response) -> None:
    error = response.error
    logger.exception(error)
    excp = traceback2.format_exc()
    data = {
        "config": deepsort_dict(app.config),
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "traceback": str(excp),
    }
    data.update(get_request_data(request))
    response.body = render("debug-error.jinja", **data)


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
        request_headers = request.env
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


def deepsort_dict(dd: dict) -> dict:
    plain = {}
    subdicts = {}
    for key, value in dd.items():
        if isinstance(value, dict):
            subdicts[key] = deepsort_dict(value)
        else:
            plain[key] = value
    return {
        **dict(sorted(plain.items())),
        **dict(sorted(subdicts.items())),
    }
