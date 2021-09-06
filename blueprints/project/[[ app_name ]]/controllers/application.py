from os import getenv

from proper import BaseController

from ..app import app
from ..models import User
from ..services import auth_services


REDIRECT_AFTER_LOGIN_KEY = "_redirect"
USER_SESSION_KEY = "_user_token"


class ApplicationController(BaseController):
    """All other controllers must inherit from this class.
    """
    def before_action(self, action):
        self._load_user()
        super().before_action(action)

    def after_action(self, action):
        self._put_security_headers()
        super().after_action(action)

    # Private

    def _load_user(self):
        user = None
        if app.config.debug:
            user = self._get_remote_user()
        self.req.user = user or self._get_user(self.resp.session)

    def _get_remote_user(self):
        """Simulate authentication for testing."""
        user_id = getenv("REMOTE_USER")
        if user_id:
            return User.by_id(user_id)

    def _get_user(self, session):
        token = session.get(USER_SESSION_KEY)
        user = auth_services.authenticate_session_token(User, token)
        if token and not user:
            del session[USER_SESSION_KEY]
            return None
        return user

    def _put_security_headers(self):
        self.resp.headers.update({
            # It determines if a web page can or cannot be included via <frame>
            # and <iframe> topics by untrusted domains.
            # https://developer.mozilla.org/Web/HTTP/Headers/X-Frame-Options
            "X-Frame-Options": "SAMEORIGIN",

            # Determine the behavior of the browser in case an XSS attack is
            # detected. Use Content-Security-Policy without allowing unsafe-inline
            # scripts instead.
            # https://developer.mozilla.org/Web/HTTP/Headers/X-XSS-Protection
            "X-XSS-Protection": "1; mode=block",

            # Download files or try to open them in the browser?
            "X-Download-Options": "noopen",

            # Set to none to restrict Adobe Flash Player’s access to the web page data.
            "X-Permitted-Cross-Domain-Policies": "none",

            "Referrer-Policy": "strict-origin-when-cross-origin",
        })


class PrivateController(ApplicationController):
    """User-only controllers can inherit from this one."""
    def before_action(self, action):
        self._require_login()
        super().before_action(action)

    def _require_login(self):
        if self.req.user:
            return
        if REDIRECT_AFTER_LOGIN_KEY not in self.resp.session:
            self.resp.session[REDIRECT_AFTER_LOGIN_KEY] = self.req.path
        self.resp.redirect_to(app.url_for("Auth.sign_in"))
