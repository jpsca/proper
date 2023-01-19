from os import getenv

from proper import request, response

from [[ app_name ]].app import config
from [[ app_name ]].models import User


USER_SESSION_KEY = "_user_token"
REMOTE_USER_ENV_VAR = "REMOTE_USER"


class LoadUser:
    def __before__(self):
        self._load_user()

    # Private

    def _load_user(self):
        user = None
        if config.debug:
            user = self._get_remote_user()
        request.user = user or self._get_user(response.session)

    def _get_remote_user(self):
        """Simulate authentication for testing."""
        user_id = getenv(REMOTE_USER_ENV_VAR)
        if user_id:
            return User.by_id(user_id)

    def _get_user(self, session):
        token = session.get(USER_SESSION_KEY)
        user = User.authenticate_session_token(token)
        if token and not user:
            del session[USER_SESSION_KEY]
            return None
        return user
