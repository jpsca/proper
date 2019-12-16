"""
## proper.error_handlers

Fallback error handlers

"""
import logging
from pathlib import Path
import traceback

import jinja2

from .support import titleize


TEMPLATES = (Path(__file__).parent / "templates").absolute()

logger = logging.getLogger("Proper")


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
    logger.error(error, exc_info=True)
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
    logger.error(resp.error, exc_info=True)
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
    return titleize(error.__class__.__name__)


def _render(template, **data):
    if not data:
        return (TEMPLATES / template).read_text()

    try:
        return _render_with_jinja(template, **data)
    except Exception as error:
        logger.error(error, exc_info=True)
        return _render("fallback-error.html")


def _include_raw(name):
    return jinja2.Markup(loader.get_source(jinja_env, name)[0])


def _render_with_jinja(template, **data):
    tmpl = jinja_env.get_template(template)
    return tmpl.render(**data)


loader = jinja2.FileSystemLoader(str(TEMPLATES))
jinja_env = jinja2.Environment(loader=loader)
jinja_env.globals['include_raw'] = _include_raw
