from os import getenv

from proper import Controller

from app.main import config
from app.models import User


USER_SESSION_KEY = "_user_token"
TEST_USER_ENV_VAR = "TEST_USER"


class RestoreSession:
    def before(self, co: Controller):
        user = None
        if config.DEBUG:
            user = self._get_test_user()
        co.request.user = user or self._get_user(co.request.session)

    # Private

    def _get_test_user(self):
        """Simulate authentication for testing."""
        user_id = getenv(TEST_USER_ENV_VAR)
        if user_id:
            return User.get_by_id(user_id)

    def _get_user(self, session):
        token = session.get(USER_SESSION_KEY)
        user = User.authenticate_session_token(token)
        if token and not user:
            del session[USER_SESSION_KEY]
            return None
        return user
