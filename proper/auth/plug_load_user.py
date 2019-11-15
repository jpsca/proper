import logging


__all__ = ("PlugLoadUser", )


logger = logging.getLogger(__name__)


def split_token(token):
    uid, mac = token.split('$', 1)
    return uid


class PlugLoadUser(object):
    def __init__(self, model, session_key="_user_token"):
        self.User = model
        self.session_key = session_key

    def __call__(self, req, resp, app):
        if resp.dispatched:
            return

        current_user = None
        if app.debug:
            current_user = self.get_remote_user(req.environ)
        req.current_user = current_user or self.get_user(req.session)

    def get_remote_user(self, environ):
        # Simulate authentication with WebTest
        login = environ.get("REMOTE_USER")
        if login:
            return self.User.by_login(login)

    def get_user(self, session):
        token = session.get(self.session_key)
        if not token:
            return None

        try:
            user_id = split_token(token)
            user = self.User.by_id(user_id)
        except ValueError:
            logger.warn("Invalid user session format. Tampered?")
            del session[self.session_key]
            return None

        if token != user.auth.get_session_token():
            logger.warn("Invalid user session. Tampered?")
            del session[self.session_key]
            return None

        return user
