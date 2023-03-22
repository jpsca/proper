import base64
import os
import typing as t

from ..constants import HEAD, GET, OPTIONS
from ..errors import InvalidCSRFToken, MissingCSRFToken

if t.TYPE_CHECKING:
    from proper import Request, Response


__all__ = ("CSRF_SESSION_KEY", "CSRF_FORM_KEY", "CSRF_HEADER", "CSRF_TOKEN_LENGTH")

CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_KEY = "csrf_token"
CSRF_HEADER = "X-CSRF-TOKEN"
CSRF_TOKEN_LENGTH = 32


class RequestForgeryProtection:
    action_name: str
    request: "Request"
    response: "Response"
    skip_csrf_check_for: tuple[str, ...] = tuple()

    def __before__(self) -> None:
        self.protect_from_forgery(self.action_name)

    def protect_from_forgery(self, action_name: str) -> None:
        """"""
        if self._must_check_csrf_token(action_name):
            self._handle_verified_request()
        else:
            self._handle_unverified_request()

        token = self.request.session.get(CSRF_SESSION_KEY)
        masked_token = self._mask_csrf_token(token) if token else None
        self.request.csrf_token = masked_token
        if masked_token:
            self.response.set_header(CSRF_HEADER, masked_token)

    def _must_check_csrf_token(self, action: str) -> bool:
        """Return wether the csrf token in the request must be checked
        for validity."""
        return (
            self.request.request_method not in (HEAD, GET, OPTIONS)
            and action not in self.skip_csrf_check_for
        )

    def _handle_verified_request(self) -> None:
        session_token = self.request.session.get(CSRF_SESSION_KEY)
        if not session_token:
            self._handle_invalid_csrf_token()
            return

        req_tokens = self._get_request_csrf_tokens()
        if not req_tokens:
            self._handle_missing_csrf_token()
            return

        if not any(session_token == req_token for req_token in req_tokens):
            self._handle_invalid_csrf_token()

    def _get_request_csrf_tokens(self) -> list[str]:
        """Get possible csrf tokens sent in the request."""
        req_tokens = [
            self._csrf_token_in_form() if self.request.content_length else None,
            self._csrf_token_in_header(),
        ]
        expected_length = CSRF_TOKEN_LENGTH * 2
        return [
            self._unmask_csrf_token(token)
            for token in req_tokens
            if token and len(token) == expected_length
        ]

    def _csrf_token_in_form(self) -> str | None:
        """Search for a CSRF token in the body data.
        Override to provide your own."""
        return self.request.form.get(CSRF_FORM_KEY)

    def _csrf_token_in_header(self) -> str | None:
        """Search for a CSRF token in a header"""
        return self.request.get_header(CSRF_HEADER)

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

    def _handle_unverified_request(self) -> None:
        session_token = self.request.session.get(CSRF_SESSION_KEY)
        if not session_token and self.request.request_method == GET:
            self._set_new_csrf_token()

    def _set_new_csrf_token(self) -> None:
        token = self._generate_csrf_token()
        self.response.session[CSRF_SESSION_KEY] = token

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
