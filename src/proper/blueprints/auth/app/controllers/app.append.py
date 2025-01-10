

class PrivateView(AppController):
    """User-only views can inherit from this one.
    """
    concerns = [
        DBConnection,
        Session,
        RestoreSession,
        RequireLogin,
        RequestForgeryProtection,
        SecurityHeaders,
    ]
