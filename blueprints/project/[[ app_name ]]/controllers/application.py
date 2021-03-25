from os import getenv

from proper import BaseController

from ..app import app
from ..models import User


REDIRECT_AFTER_LOGIN_KEY = "_redirect"
USER_SESSION_KEY = "_user_token"


class ApplicationController(BaseController):
    """All other controllers must inherit from this class."""

    def before_action(self, req, resp, action):
        self._load_user(req, resp)
        super().before_action(req, resp, action)

    def after_action(self, req, resp, action):
        self._put_security_headers(req, resp)
        super().after_action(req, resp, action)

    def _load_user(self, req, resp):
        user = None
        if app.config.debug:
            user = self._get_remote_user()
        req.user = user or self._get_user(resp.session)

    def _get_remote_user(self):
        """Simulate authentication for testing."""
        user_id = getenv("REMOTE_USER")
        if user_id:
            return User.by_id(user_id)

    def _get_user(self, session):
        token = session.get(USER_SESSION_KEY)
        user = User.authenticate_session_token(token)
        if token and not user:
            del session[USER_SESSION_KEY]
            return None
        return user

    def _put_security_headers(self, req, resp):
        resp.headers.update(
            {
                # It determines if a web page can or cannot be included via <frame>
                # and <iframe> topics by untrusted domains.
                # https://developer.mozilla.org/Web/HTTP/Headers/X-Frame-Options
                "X-Frame-Options": "SAMEORIGIN",
                # Determine the behavior of the browser in case an XSS attack is
                # detected. Use Content-Security-Policy without allowing unsafe-inline
                # scripts instead.
                # https://developer.mozilla.org/Web/HTTP/Headers/X-XSS-Protection
                "X-XSS-Protection": "1; mode=block",
                # Prevents browsers from interpreting files as something else than
                # declared by the content type in the HTTP headers.
                # https://developer.mozilla.org/Web/HTTP/Headers/X-Content-Type-Options
                "X-Content-Type-Options": "nosniff",
                # Download files or try to open them in the browser?
                "X-Download-Options": "noopen",
                # Set to none to restrict Adobe Flash Player’s access to the web page data.
                "X-Permitted-Cross-Domain-Policies": "none",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            }
        )


class PrivateController(ApplicationController):
    def before_action(self, req, resp, action):
        self._require_login(req, resp)
        super().before_action(req, resp, action)

    def _require_login(self, req, resp):
        if req.user:
            return
        if REDIRECT_AFTER_LOGIN_KEY not in resp.session:
            resp.session[REDIRECT_AFTER_LOGIN_KEY] = req.path
        resp.redirect_to(app.url_for("Auth.sign_in"))
