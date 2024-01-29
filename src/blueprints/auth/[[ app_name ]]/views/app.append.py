

class PrivateView(AppView):
    """User-only views can inherit from this one.
    """
    concerns = [
        DBConnection,
        Session,
        LoadUser,
        RequireLogin,
        RequestForgeryProtection,
        SecurityHeaders,
    ]
