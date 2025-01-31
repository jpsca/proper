

class PrivateController(AppController):
    """User-only controllers can inherit from this one.
    """
    concerns = [
        DBConnection,
        Session,
        RestoreUser,
        RequireLogin,
        RequestForgeryProtection,
        SecurityHeaders,
    ]
