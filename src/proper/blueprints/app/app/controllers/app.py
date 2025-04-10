from proper import Controller
from proper.concerns import (
    RequestForgeryProtection,
    RestoreSession,
    UpdateSessionCookie,
)

from .concerns.security_headers import SetSecurityHeaders


class AppController(Controller):
    """All other controllers must inherit from this class.
    """
    # Note: The order might matter
    before = [
        RestoreSession(),
        RequestForgeryProtection(),
    ]
    after = [
        UpdateSessionCookie(),
        SetSecurityHeaders(),
    ]
