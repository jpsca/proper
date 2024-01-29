from os import getenv

from proper import View

from [[ app_name ]].app import config
from [[ app_name ]].models import User


USER_SESSION_KEY = "_user_token"
REMOTE_USER_ENV_VAR = "REMOTE_USER"


class LoadUser:
    def before(self, view: View):
        user = None
        if config.DEBUG:
            user = self._get_remote_user()
        view.request.user = user or self._get_user(view.response.session)

    def after(self, view: View):
        pass

    # Private

    def _get_remote_user(self):
        """Simulate authentication for testing."""
        user_id = getenv(REMOTE_USER_ENV_VAR)
        if user_id:
            return User.get_by_id(user_id)

    def _get_user(self, session):
        token = session.get(USER_SESSION_KEY)
        user = User.authenticate_session_token(token)
        if token and not user:
            del session[USER_SESSION_KEY]
            return None
        return user
