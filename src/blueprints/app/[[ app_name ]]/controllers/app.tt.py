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
        SecurityHeaders,
    ]


class PrivateController(AppController):
    """User-only controllers can inherit from this one.
    """
    # The order matters
    concerns = AppController.concerns + [
        RequestForgeryProtection,
    ]
