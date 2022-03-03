"""
Fallback error handlers

"""
import logging
import traceback
from pathlib import Path

import inflection
from markupsafe import Markup

from .constants import GET
from .helpers import Render


logger = logging.getLogger("proper")

TEMPLATES = (Path(__file__).parent / "templates").absolute()
jinja_render = Render(TEMPLATES)


def _include_raw(name):
    return Markup(jinja_render.loader.get_source(jinja_render.env, name)[0])


jinja_render.globals["include_raw"] = _include_raw


def render(template, **data):
    if not data:
        return (TEMPLATES / template).read_text()
    try:
        return jinja_render(template, **data)
    except Exception:
        logger.exception("")
        return render("fallback-error.html")


def debug_not_found_handler(req, resp, app):
    if is_index(req):
        return render_default_index(resp)

    error = resp.error
    data = {
        "resp": resp,
        "title": get_title(error),
        "description": str(error),
        "routes": app.routes,
    }
    data.update(get_request_data(req))
    resp.body = render("debug-not-found.html.jinja", **data)


def is_index(req):
    return req.method == GET and req.path == "/"


def render_default_index(resp):
    data = {
        "proper_version": "",
        "python_version": "",
    }
    resp.body = render("default-index.html.jinja", **data)


def debug_error_handler(req, resp, _app):
    error = resp.error
    logger.exception(error)
    excp = traceback.format_exc()
    data = {
        "resp": resp,
        "title": get_title(error),
        "description": str(error),
        "traceback": excp,
    }
    data.update(get_request_data(req))
    resp.body = render("debug-error.html.jinja", **data)


def get_title(error):
    return inflection.titleize(error.__class__.__name__)


def get_request_data(req):
    try:
        req_query = req.query
    except Exception:
        req_query = None
    try:
        req_form = req.form
    except Exception:
        req_form = None
    try:
        req_files = req.files
    except Exception:
        req_files = None
    try:
        req_headers = req.headers
    except Exception:
        req_headers = None
    return {
        "req_query": req_query,
        "req_form": req_form,
        "req_files": req_files,
        "req_headers": req_headers,
    }


def fallback_not_found_handler(req, resp, _app):
    resp.body = render("fallback-not-found.html")


def fallback_forbidden_handler(_req, resp, _app):
    resp.body = render("fallback-forbidden.html")


def fallback_error_handler(req, resp, _app):
    logger.exception(resp.error)
    resp.body = render("fallback-error.html")
