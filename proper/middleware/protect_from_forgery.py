"""
Requires `proper.middleware.session`.

"""
import uuid

from ..errors import InvalidCSRFToken
from ..errors import MissingCSRFToken


__all__ = (
    "protect_from_forgery",
    "put_csrf_header",
    "CSRF_SESSION_KEY",
    "CSRF_QUERY_KEY",
    "CSRF_HEADER",
    "CSRF_HEADER_ALT",
)

CSRF_SESSION_KEY = "__csrf_token"
CSRF_QUERY_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRF-TOKEN"
CSRF_HEADER_ALT = "X-CSRFToken"


def protect_from_forgery(req, resp, app):
    """
    """
    req_token = get_or_set_token(req, resp)
    if not req.must_check_csrf():
        return

    token = get_used_token(req)
    if not token:
        raise MissingCSRFToken(
            "Missing Cross-Site Request Forgery (CSRF) token. "
            f"You must provide the token value as a “{CSRF_QUERY_KEY}” form field, "
            f"a query field with the same name, or in a “{CSRF_HEADER}” header."
        )

    if req_token != token:
        raise InvalidCSRFToken(
            "Invalid Cross-Site Request Forgery (CSRF) token. "
            "The token provided doesn't match the one stored in the session."
        )


def put_csrf_header(req, resp, app):
    token = get_or_set_token(req, resp)
    resp.headers[CSRF_HEADER] = token


def get_used_token(req):
    return (
        req.query.get(CSRF_QUERY_KEY)
        or req.headers.get(CSRF_HEADER)
        or req.headers.get(CSRF_HEADER_ALT)
        or (req.form.get(CSRF_QUERY_KEY) if req.content_length else None)
    )


def get_or_set_token(req, resp):
    token = req.session.get(CSRF_SESSION_KEY)
    if not token:
        token = make_new_token()
        resp.session[CSRF_SESSION_KEY] = token
    req.csrf_token = token
    return token


def make_new_token():
    return str(uuid.uuid4()).replace("-", "")
