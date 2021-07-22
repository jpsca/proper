"""
Fallback error handlers

"""
import logging
import traceback
from pathlib import Path

import inflection
from markupsafe import Markup

from proper.helpers import Render


logger = logging.getLogger("proper")

TEMPLATES = (Path(__file__).parent / "templates").absolute()
jinja_render = Render(TEMPLATES)


def _include_raw(name):
    return Markup(jinja_render.loader.get_source(jinja_render.env, name)[0])


jinja_render.globals["include_raw"] = _include_raw


def debug_not_found_handler(req, resp, app):
    error = resp.error
    data = {
        "resp": resp,
        "title": _get_title(error),
        "description": str(error),
        "routes": app.routes,
    }
    data.update(_get_req_data(req))
    resp.body = _render("debug-not-found.html.jinja", **data)


def debug_error_handler(req, resp, _app):
    error = resp.error
    logger.exception(error)
    excp = traceback.format_exc()
    data = {
        "resp": resp,
        "title": _get_title(error),
        "description": str(error),
        "traceback": excp,
    }
    data.update(_get_req_data(req))
    resp.body = _render("debug-error.html.jinja", **data)


def fallback_not_found_handler(req, resp, _app):
    resp.body = _render("fallback-not-found.html")


def fallback_forbidden_handler(_req, resp, _app):
    resp.body = _render("fallback-forbidden.html")


def fallback_error_handler(req, resp, _app):
    logger.exception(resp.error)
    resp.body = _render("fallback-error.html")


def _get_req_data(req):
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


def _get_title(error):
    return inflection.titleize(error.__class__.__name__)


def _render(template, **data):
    if not data:
        return (TEMPLATES / template).read_text()
    try:
        return jinja_render(template, **data)
    except Exception:
        logger.exception("")
        return _render("fallback-error.html")
