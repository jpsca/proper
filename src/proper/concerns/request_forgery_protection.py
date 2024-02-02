import base64
import os
import typing as t

from proper.constants import GET, HEAD, OPTIONS, QUERY
from proper.errors import InvalidCSRFToken, MissingCSRFToken


if t.TYPE_CHECKING:
    from proper.request import Request
    from proper.response import Response
    from proper.view import View


__all__ = (
    "RequestForgeryProtection",
    "CSRF_SESSION_KEY",
    "CSRF_FORM_KEY",
    "CSRF_HEADER",
    "CSRF_TOKEN_LENGTH",
)

SKIP_FOR_METHODS = (HEAD, GET, OPTIONS, QUERY)
CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_KEY = "csrf_token"
CSRF_HEADER = "x_csrf_token"
CSRF_TOKEN_LENGTH = 32


class RequestForgeryProtection:
    action_name: str
    skip_for: t.Iterable[str] = ()

    def __init__(self, *, skip_for: t.Iterable[str] = ()) -> None:
        self.skip_for = skip_for or ()

    def before(self, view: "View") -> None:
        request = view.request
        response = view.response

        if self._must_check_csrf_token(request):
            token = self._handle_verified_request(request)
        else:
            token = self._handle_unverified_request(request, response)

        if not token:
            return

        masked_token = self._mask_csrf_token(token)
        request.csrf_token = masked_token
        response.headers[CSRF_HEADER] = masked_token

    def after(self, view: "View") -> None:
        pass

    # Private

    def _must_check_csrf_token(self, request: "Request") -> bool:
        """Return wether the csrf token in the request must be checked
        for validity."""
        return bool(
            request.method not in SKIP_FOR_METHODS
            and request.matched_action
            and request.matched_action not in self.skip_for
        )

    def _handle_verified_request(self, request: "Request") -> None:
        session_token = request.session.get(CSRF_SESSION_KEY)
        if not session_token:
            self._handle_invalid_csrf_token()

        req_tokens = self._get_request_csrf_tokens(request)

        if not req_tokens:
            self._handle_missing_csrf_token()

        if not any(session_token == req_token for req_token in req_tokens):
            self._handle_invalid_csrf_token()

        return session_token

    def _get_request_csrf_tokens(self, request: "Request") -> list[str]:
        """Get possible csrf tokens sent in the request."""
        req_tokens = [
            self._csrf_token_in_form(request),
            self._csrf_token_in_header(request),
        ]
        expected_length = CSRF_TOKEN_LENGTH * 2
        return [
            self._unmask_csrf_token(token)
            for token in req_tokens
            if token and len(token) == expected_length
        ]

    def _csrf_token_in_form(self, request: "Request") -> str:
        """Search for a CSRF token in the body data.
        Override to provide your own."""
        if not request.form:
            return ""
        return request.form.get(CSRF_FORM_KEY, "")

    def _csrf_token_in_header(self, request: "Request") -> str:
        """Search for a CSRF token in a header"""
        return request.get(CSRF_HEADER, "")

    def _set_new_csrf_token(self, response: "Response") -> str:
        token = self._generate_csrf_token()
        response.session[CSRF_SESSION_KEY] = token
        return token

    def _handle_unverified_request(self, request: "Request", response: "Response") -> str:
        session_token = request.session.get(CSRF_SESSION_KEY) or ""
        if not session_token and request.method == GET:
            session_token = self._set_new_csrf_token(response)
        return session_token

    def _handle_invalid_csrf_token(self) -> None:
        raise InvalidCSRFToken(
            "Invalid CSRF (Cross-Site Request Forgery) token. "
            "The token provided doesn't match the one stored in the session."
        )

    def _handle_missing_csrf_token(self) -> None:
        raise MissingCSRFToken(
            "Missing CSRF (Cross-Site Request Forgery) token. "
            f"You must provide the token value as a “{CSRF_FORM_KEY}” form field "
            f"or in a “{CSRF_HEADER}” header."
        )

    def _generate_csrf_token(self) -> str:
        token = base64.urlsafe_b64encode(os.urandom(CSRF_TOKEN_LENGTH))
        return token[:CSRF_TOKEN_LENGTH].decode()

    def _mask_csrf_token(self, token: str) -> str:
        """Creates a masked version of the CSRF token that varies
        on each request. The masking is used to mitigate SSL attacks
        like BREACH.
        """
        random_prefix = self._generate_csrf_token()
        return f"{random_prefix}{token}"

    def _unmask_csrf_token(self, token: str) -> str:
        return token[CSRF_TOKEN_LENGTH:]
