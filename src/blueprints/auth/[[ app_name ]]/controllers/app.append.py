

class PrivateController(AppController):
    """User-only controllers can inherit from this one.
    """
    middleware = [
        DBConnection,
        Session,
        LoadUser,
        RequireLogin,
        RequestForgeryProtection,
        SecurityHeaders,
    ]
