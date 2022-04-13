"""
Fallback error handlers

"""
import logging
import pkg_resources
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import inflection
from markupsafe import Markup

from .constants import GET
from .helpers import Render

if TYPE_CHECKING:
    from typing import Any
    from proper import App, Request, Response


logger = logging.getLogger("proper")

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
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "routes": app.routes,
    }
    data.update(get_request_data(request))
    response.body = render("debug-not-found.html.jinja", **data)


def is_index(request: "Request") -> bool:
    return request.method == GET and request.path == "/"


def render_default_index(response: "Response") -> None:
    data = {
        "proper_version": pkg_resources.get_distribution("proper").version,
        "python_version": sys.version,
    }
    response.body = render("default-index.html.jinja", **data)


def debug_error_handler(request: "Request", response: "Response", _app: "App") -> None:
    error = response.error
    logger.exception(error)
    excp = traceback.format_exc()
    data = {
        "response": response,
        "title": get_title(error),
        "description": str(error),
        "traceback": excp,
    }
    data.update(get_request_data(request))
    response.body = render("debug-error.html.jinja", **data)


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
        request_files = request.files
    except Exception:
        request_files = None
    try:
        request_headers = request.headers
    except Exception:
        request_headers = None
    return {
        "request_query": request_query,
        "request_form": request_form,
        "request_files": request_files,
        "request_headers": request_headers,
    }


def fallback_not_found_handler(
    _request: "Request", response: "Response", _app: "App"
) -> None:
    response.body = render("fallback-not-found.html")


def fallback_forbidden_handler(
    _request: "Request", response: "Response", _app: "App"
) -> None:
    response.body = render("fallback-forbidden.html")


def fallback_error_handler(
    _request: "Request", response: "Response", _app: "App"
) -> None:
    logger.exception(response.error)
    response.body = render("fallback-error.html")
