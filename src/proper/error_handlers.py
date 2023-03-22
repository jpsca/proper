"""
Fallback error handlers

"""
import pkg_resources
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import inflection
from markupsafe import Markup

from .config import logger
from .constants import GET
from .helpers import Render

if TYPE_CHECKING:
    from typing import Any
    from proper import App, Request, Response


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


def debug_not_found_handler(
    request: "Request", response: "Response", app: "App"
) -> None:
    if is_index(request):
        return render_default_index(response)

    error = response.error
    data = {
        "config": deepsort_dict(app.config),
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "routes": app.routes,
    }
    data.update(get_request_data(request))
    response.body = render("debug-not-found.jinja", **data)


def is_index(request: "Request") -> bool:
    return request.method == GET and request.path == "/"


def render_default_index(response: "Response") -> None:
    data = {
        "proper_version": pkg_resources.get_distribution("proper").version,
        "python_version": sys.version,
    }
    response.body = render("default-index.jinja", **data)


def debug_error_handler(request: "Request", response: "Response", app: "App") -> None:
    error = response.error
    logger.exception(error)
    excp = traceback.format_exc()
    data = {
        "config": deepsort_dict(app.config),
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "traceback": excp,
    }
    data.update(get_request_data(request))
    response.body = render("debug-error.jinja", **data)


def get_title(error: "Any") -> str:
    return inflection.titleize(error.__class__.__name__)


def get_request_data(request: "Request") -> dict:
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


def fallback_not_found_handler(
    _request: "Request", response: "Response", app: "App"
) -> None:
    response.body = render("fallback-not-found.html")


def fallback_forbidden_handler(
    _request: "Request", response: "Response", app: "App"
) -> None:
    response.body = render("fallback-forbidden.html")


def fallback_error_handler(
    _request: "Request", response: "Response", app: "App"
) -> None:
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
