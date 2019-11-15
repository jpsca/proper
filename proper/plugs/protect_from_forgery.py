"""
## proper.plugs.protect_from_forgery

Requires `plugs.session`.

"""
import uuid

from ..errors import InvalidCSRFToken
from ..errors import MissingCSRFToken


__all__ = (
    "protect_from_forgery",
    "CSRF_SESSION_KEY",
    "CSRF_QUERY_KEY",
    "CSRF_HEADER",
    "CSRF_HEADER_ALT",
)

CSRF_SESSION_KEY = "__csrf_token"
CSRF_QUERY_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRFToken"
CSRF_HEADER_ALT = "X-CSRF-TOKEN"


def protect_from_forgery(req, resp, app):
    if resp.dispatched:
        return

    get_or_set_token(req)

    if not req.must_check_csrf():
        return

    token = get_used_token(req)
    if not token:
        raise MissingCSRFToken(
            "Missing Cross-Site Request Forgery (CSRF) token. "
            f"You must provide the token value as a “{CSRF_QUERY_KEY}” form field, "
            f"a query field with the same name, or in a “{CSRF_HEADER}” header."
        )

    if not request_token_is_valid(req, token):
        raise InvalidCSRFToken(
            "Invalid Cross-Site Request Forgery (CSRF) token. "
            "The token provided doesn't match the one stored in the session."
        )


def request_token_is_valid(req, token):
    return get_or_set_token(req) == token


def get_used_token(req):
    return (
        req.query.get(CSRF_QUERY_KEY)
        or req.environ.get(CSRF_HEADER)
        or req.environ.get(CSRF_HEADER_ALT)
        or (req.form.get(CSRF_QUERY_KEY) if req.content_length else None)
    )


def get_or_set_token(req):
    token = req.session.get(CSRF_SESSION_KEY)
    if not token:
        token = make_new_token()
        req.session[CSRF_SESSION_KEY] = token
    req.csrf_token = token
    return token


def make_new_token():
    return str(uuid.uuid4()).replace("-", "")
