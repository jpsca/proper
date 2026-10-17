import base64
import hmac
import os

from ..constants import GET, HEAD, OPTIONS, QUERY
from ..errors import InvalidCSRFToken, MissingCSRFToken
from ..global_context import current
from .concern import Concern


__all__ = (
    "CSRF_FORM_KEY",
    "CSRF_HEADER",
    "CSRF_SESSION_KEY",
    "CSRF_TOKEN_LENGTH",
    "RequestForgeryProtection",
)
SKIP_FOR_METHODS = (HEAD, GET, OPTIONS, QUERY)
CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_KEY = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
CSRF_TOKEN_LENGTH = 32
# the base64 of a one-time pad and the token XORed with it
_MASKED_LENGTH = len(base64.urlsafe_b64encode(bytes(CSRF_TOKEN_LENGTH * 2)))


class RequestForgeryProtection(Concern):
    """Legacy token-based Cross-Site Request Forgery protection for state-changing requests
    (POST, PATCH, PUT, and DELETE).

    For modern browser-based applications (post 2020), you probably DON'T want to use
    this concern, and should instead use the `OriginProtection` concern.

    """
    before = {"do": "check_csrf_token"}

    def check_csrf_token(self) -> None:
        if self.request.method not in SKIP_FOR_METHODS:
            token = self._handle_verified_request()
        else:
            token = self._handle_unverified_request()

        masked_token = self._mask_csrf_token(token)
        current.csrf_token = masked_token
        self.response.headers[CSRF_HEADER] = masked_token

    # Private

    def _handle_verified_request(self) -> str:
        session_token = self.request.session.get(CSRF_SESSION_KEY)
        if not session_token:
            self._handle_invalid_csrf_token()

        req_tokens = self._get_request_csrf_tokens()

        if not req_tokens:
            self._handle_missing_csrf_token()

        expected = (session_token or "").encode()
        if not any(hmac.compare_digest(expected, req_token) for req_token in req_tokens):
            self._handle_invalid_csrf_token()

        # The ` or ""` is to satisfy type checkers that session_token is always a
        # string, even though it should never be `None` at this point.
        return session_token or ""

    def _get_request_csrf_tokens(self) -> list[bytes]:
        """Get possible csrf tokens sent in the self.request."""
        req_tokens = [
            self._csrf_token_in_form(),
            self._csrf_token_in_header(),
        ]
        return [
            self._unmask_csrf_token(token)
            for token in req_tokens
            if token and len(token) == _MASKED_LENGTH
        ]

    def _csrf_token_in_form(self) -> str:
        """Search for a CSRF token in the body data.
        Override to provide your own."""
        if not self.request.form:
            return ""
        return self.request.form.get(CSRF_FORM_KEY, "")

    def _csrf_token_in_header(self) -> str:
        """Search for a CSRF token in a header"""
        return self.request.headers.get("x-csrf-token") or ""

    def _set_new_csrf_token(self) -> str:
        token = self._generate_csrf_token()
        self.response.session[CSRF_SESSION_KEY] = token
        return token

    def _handle_unverified_request(self) -> str:
        session_token = self.request.session.get(CSRF_SESSION_KEY) or ""
        if not session_token and self.request.method == GET:
            session_token = self._set_new_csrf_token()
        return session_token

    def _handle_invalid_csrf_token(self) -> None:
        raise InvalidCSRFToken(
            "Invalid CSRF (Cross-Site Request Forgery) token. "
            "The token provided doesn't match the one stored in the session."
        )

    def _handle_missing_csrf_token(self) -> None:
        raise MissingCSRFToken(
            "Missing CSRF (Cross-Site Request Forgery) token. "
            f'You must provide the token value as a "{CSRF_FORM_KEY}" form field '
            f'or in a "{CSRF_HEADER}" header.'
        )

    def _generate_csrf_token(self) -> str:
        token = base64.urlsafe_b64encode(os.urandom(CSRF_TOKEN_LENGTH))
        return token[:CSRF_TOKEN_LENGTH].decode()

    def _mask_csrf_token(self, token: str) -> str:
        """Creates a masked version of the CSRF token that varies on each self.request:
        a random one-time pad followed by the token XORed with it, in base64.
        No part of the token repeats between responses, so a compression attack
        like BREACH can't guess it.
        """
        raw = token.encode()
        pad = os.urandom(len(raw))
        return base64.urlsafe_b64encode(pad + _xor(pad, raw)).decode()

    def _unmask_csrf_token(self, token: str) -> bytes:
        try:
            masked = base64.urlsafe_b64decode(token)
        except ValueError:  # not base64 (`binascii.Error`), or not ASCII
            return b""
        if len(masked) != CSRF_TOKEN_LENGTH * 2:
            return b""
        return _xor(masked[:CSRF_TOKEN_LENGTH], masked[CSRF_TOKEN_LENGTH:])


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b, strict=True))
