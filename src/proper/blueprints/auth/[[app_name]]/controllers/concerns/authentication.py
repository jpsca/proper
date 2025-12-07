from proper import Concern, g

from ...main import app
from ...models import Session, User


class Authentication(Concern):
    skip_authentication = False

    def before(self):
        self.require_authentication()
        super().before()

    def require_authentication(self):
        if self.skip_authentication or self.is_authenticated():
            return
        if not self._resume_session():
            self._request_authentication()

    def is_authenticated(self):
        return g.session is not None

    def new_session_for(self, user: User):
        session = Session.create_for_user(
            user=user,
            ip_address=self.request.remote_ip,
            user_agent=self.request.user_agent,
        )
        return self._set_current_session(session)

    def terminate_session(self):
        if g.session:
            g.session.delete_instance()
            g.session = None

        self.request.user = None
        self.response.set_signed_cookie("_auth", "", max_age=0)
        # Clear the session on logout to avoid leaking data between users
        self.response.session.clear()

    def redirect_after_authentication(self, *, default="/", flash=None):
        redirect_path = self.response.session.pop("_redirect", default)
        self.response.redirect_to(redirect_path, flash=flash)

    # Private

    def _request_authentication(self):
        self.response.session.setdefault("_redirect", self.request.path)
        self.response.redirect_to(app.url_for("Session.new"))

    def _resume_session(self):
        if session := self._find_session_by_cookie():
            session.touch()
            return self._set_current_session(session)

    def _find_session_by_cookie(self):
        token = self.request.get_signed_cookie("_auth")
        if token:
            return Session.find_by_token(token)

    def _set_current_session(self, session):
        g.session = session
        self.request.user = session.user
        self.response.set_signed_cookie(
            "_auth",
            session.token,
            httponly=True,
            secure=self.request.is_secure,
            samesite="Lax",
        )
        return session
