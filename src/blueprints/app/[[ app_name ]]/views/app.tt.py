from proper import View

from .concerns.db_connection import DBConnection
from .concerns.security_headers import SecurityHeaders


class AppView(View):
    """All other views must inherit from this class.
    """
    concerns = [
        DBConnection,
        SecurityHeaders,
    ]
