

class PrivateController(BaseController):
    """User-only controllers can inherit from this one.
    """
    before = [
        RestoreSession(),
        RestoreUser(),
        RequireLogin(),
        RequestForgeryProtection(),
    ]
    after = [
        UpdateSessionCookie(),
        SetSecurityHeaders(),
    ]
