from os import getenv

from proper import Controller, request, response

from [[ app_name ]].app import app, config
from [[ app_name ]].models import User


REDIRECT_AFTER_LOGIN_KEY = "_redirect"
USER_SESSION_KEY = "_user_token"


class AppController(Controller):
    """All other controllers must inherit from this class.
    """
    def before_action(self):
        self._load_user()

    def after_action(self):
        self._put_security_headers()

    # Private

    def _put_security_headers(self):
        response.headers.update({
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

    def _load_user(self):
        user = None
        if config.debug:
            user = self._get_remote_user()
        request.user = user or self._get_user(response.session)

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


class PrivateController(AppController):
    """User-only controllers can inherit from this one."""
    def before_action(self):
        self._require_login()

    # Private

    def _require_login(self):
        if request.user:
            return
        if REDIRECT_AFTER_LOGIN_KEY not in response.session:
            response.session[REDIRECT_AFTER_LOGIN_KEY] = request.path
        response.redirect_to(app.url_for("Auth.sign_in"))
