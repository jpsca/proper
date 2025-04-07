from proper import Controller
from proper.concerns import RequestForgeryProtection, RestoreSession, UpdateSessionCookie

from .concerns.db_connection import DBConnection
from .concerns.security_headers import SecurityHeaders


class AppController(Controller):
    """All other controllers must inherit from this class.
    """
    # Note: The order might matter
    before = [
        DBConnection(),
        RestoreSession(),
        RequestForgeryProtection(),
    ]
    after = [
        UpdateSessionCookie(),
        SecurityHeaders(),
    ]
