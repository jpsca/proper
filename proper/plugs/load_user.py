__all__ = ("LoadUser",)


def split_token(token):
    uid, mac = token.split("$", 1)
    return uid


class LoadUser(object):
    """Reads the user_token from the session and store the user object in the
    request at `req.current_user`.

    Arguments:

    - `user_by_id()`: Function to query for a "user" object by id.

    """

    def __init__(self, user_by_id, *, session_key="_user_token"):
        self.user_by_id = user_by_id
        self.session_key = session_key

    def __call__(self, req, resp, app):
        if resp.dispatched:
            return

        current_user = None
        if app.debug:
            current_user = self.get_remote_user(req.environ)
        req.current_user = current_user or self.get_user(resp.session)

    def get_remote_user(self, environ):
        """Simulate authentication for testing.
        Reads the user_id from the REMOTE_USER env variable.
        """
        user_id = environ.get("REMOTE_USER")
        if user_id:
            return self.user_by_id(user_id)

    def get_user(self, session):
        token = session.get(self.session_key)
        if not token:
            return None

        try:
            user_id = split_token(token)
            user = self.user_by_id(user_id)
        except ValueError:
            del session[self.session_key]
            return None

        if not user or token != user.get_session_token():
            del session[self.session_key]
            return None

        return user
