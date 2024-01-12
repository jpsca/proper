

class PrivateView(AppView):
    """User-only views can inherit from this one.
    """
    middleware = [
        DBConnection,
        Session,
        LoadUser,
        RequireLogin,
        RequestForgeryProtection,
        SecurityHeaders,
    ]
