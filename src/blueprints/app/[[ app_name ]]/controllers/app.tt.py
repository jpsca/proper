from proper import Controller

from .concerns.db_connection import DBConnection
from .concerns.security_headers import SecurityHeaders


class AppController(Controller):
    """All other controllers must inherit from this class.
    """
    middleware = [
        DBConnection,
        SecurityHeaders,
    ]
