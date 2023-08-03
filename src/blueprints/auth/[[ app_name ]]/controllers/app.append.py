from proper import RequestForgeryProtection, Session
from .concerns import LoadUser, RequireLogin

class PrivateController(
    Session,
    LoadUser,
    RequireLogin,
    RequestForgeryProtection,
    AppController,
):
    """User-only controllers can inherit from this one."""
    pass
