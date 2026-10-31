from collections.abc import Sequence

from proper.constants import AUTH_COOKIE_NAME, AUTH_COOKIE_SALT
from proper.global_context import current
from proper.models import ProperModel
from .concern import Concern
from .request_forgery_protection import CSRF_SESSION_KEY


class Authentication(Concern):
    Session: type[ProperModel]

    auth_cookie_name: str = AUTH_COOKIE_NAME
    auth_cookie_salt: str = AUTH_COOKIE_SALT

    before = {"do": "require_authentication"}
    skip_authentication: bool | Sequence = ()

    def require_authentication(self):
        """Restores the session of the auth cookie, if there is one, so
        `current.user` is known on every page, public ones too. Then, if
        the action is not public, sends a visitor without a session to the
        sign-in page."""
        if not self.is_authenticated():
            self._resume_session()
        if self.is_authenticated() or self.authentication_is_skipped():
            return
        self._request_authentication()

    def authentication_is_skipped(self) -> bool:
        """Whether `skip_authentication` makes the matched action public."""
        skip = self.skip_authentication
        if isinstance(skip, bool):
            return skip
        if isinstance(skip, str):
            # One action name, not the letters of one
            return self.request.matched_action == skip
        return self.request.matched_action in skip

    def is_authenticated(self) -> bool:
        return current.auth_session is not None

    def new_session_for(self, user: ProperModel) -> ProperModel:
        session = self.Session.create_for_user(  # type: ignore
            user=user,
            ip_address=self.request.remote_ip,
            user_agent=self.request.user_agent,
        )
        # A new CSRF token for the signed-in user: one that someone else
        # planted in the cookie session (from a sibling subdomain) stops
        # working. The rest of the session stays, like a cart.
        self.response.session.pop(CSRF_SESSION_KEY, None)
        return self._set_current_session(session)

    def terminate_session(self):
        if current.auth_session:
            current.auth_session.delete_instance()
            current.auth_session = None
        current.user = None
        self.response.set_signed_cookie(self.auth_cookie_name, "", max_age=0)
        # Clear the session on logout to avoid leaking data between users
        self.response.session.clear()

    def redirect_if_authenticated(self, *, default="/", flash=None):
        if not self.is_authenticated():
            # `require_authentication` already did this when it ran before;
            # it is for a callback list that calls this method on its own.
            self._resume_session()
        if self.is_authenticated():
            self.redirect_after_authentication(default=default, flash=flash)

    def redirect_after_authentication(self, *, default="/", flash=None):
        redirect_path = self.response.session.pop("_redirect", default)
        self.response.redirect_to(redirect_path, flash=flash)

    # Private

    def _request_authentication(self):
        self.response.session.setdefault("_redirect", self.request.path)
        self.response.redirect_to("Session.new")

    def _resume_session(self) -> ProperModel | None:
        if session := self._find_session_by_cookie():
            session.touch()  # type: ignore
            return self._set_current_session(session)

    def _find_session_by_cookie(self) -> ProperModel | None:
        token = self.request.get_signed_cookie(
            self.auth_cookie_name,
            salt=self.auth_cookie_salt,
        )
        if token:
            return self.Session.find_by_token(token)  # type: ignore

    def _set_current_session(self, session: ProperModel) -> ProperModel:
        current.auth_session = session
        current.user = session.user  # type: ignore
        self.response.set_signed_cookie(
            self.auth_cookie_name,
            session.token,  # type: ignore
            httponly=True,
            secure=self.request.is_secure,
            samesite="Lax",
            salt=self.auth_cookie_salt,
        )
        return session
