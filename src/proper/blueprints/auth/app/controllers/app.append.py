

class PrivateController(AppController):
    """User-only controllers can inherit from this one.
    """
    before = [
        DBConnection(),
        RestoreSession(),
        RestoreUser(),
        RequireLogin(),
        RequestForgeryProtection(),
    ]
    after = [
        UpdateSessionCookie(),
        SecurityHeaders(),
    ]
