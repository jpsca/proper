

class PrivateController(
    Session,
    LoadUser,
    RequireLogin,
    RequestForgeryProtection,
    AppController,
):
    """User-only controllers can inherit from this one."""
    pass
