from proper import Controller
from proper.concerns import RequestForgeryProtection, Session

from .concerns.db_connection import DBConnection
from .concerns.security_headers import SecurityHeaders


class AppController(Controller):
    """All other controllers must inherit from this class.
    """
    # The order matters
    concerns = [
        DBConnection,
        Session,
        RequestForgeryProtection,
        SecurityHeaders,
    ]
