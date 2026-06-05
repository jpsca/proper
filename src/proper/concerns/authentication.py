import typing as t
from collections.abc import Sequence

from proper.constants import AUTH_COOKIE_NAME, AUTH_COOKIE_SALT
from proper.global_context import current
from proper.models import ProperModel
from .concern import Concern


class Authentication(Concern):
    _Session: type[ProperModel]
    auth_cookie_name: str = AUTH_COOKIE_NAME
    auth_cookie_salt: str = AUTH_COOKIE_SALT

    before = {"do": "require_authentication"}
    skip_authentication: bool | Sequence = ()

    @classmethod
    def for_session(
        cls,
        Session: type[ProperModel],
        *,
        auth_cookie_name: str = AUTH_COOKIE_NAME,
        auth_cookie_salt: str = AUTH_COOKIE_SALT,
    ) -> type[t.Self]:
        """Factory method to create an Authentication concern class for a specific Session model."""
        cls._Session = Session
        cls.auth_cookie_name = auth_cookie_name
        cls.auth_cookie_salt = auth_cookie_salt
        return cls

    def require_authentication(self):
        if self.is_authenticated():
            return
        elif isinstance(self.skip_authentication, bool):
            if self.skip_authentication:
                return
        elif self.request.matched_action in self.skip_authentication:
            return
        if not self._resume_session():
            self._request_authentication()

    def is_authenticated(self) -> bool:
        return current.auth_session is not None

    def new_session_for(self, user: ProperModel) -> ProperModel:
        session = self._Session.create_for_user(  # type: ignore
            user=user,
            ip_address=self.request.remote_ip,
            user_agent=self.request.user_agent,
        )
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
            # The session was not loaded if authentication was skipped,
            # so we try to load it now.
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
            return self._Session.find_by_token(token)  # type: ignore

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
