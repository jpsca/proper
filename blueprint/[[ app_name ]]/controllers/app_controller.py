from proper import Controller
from proper.concerns import (
    RateLimiting,
    RequestForgeryProtection,
)

from .concerns.security_headers import SecurityHeaders


class AppController(
    Controller,
    RateLimiting,
    RequestForgeryProtection,
    SecurityHeaders,
):
    """All other controllers must inherit from this class.
    """
    pass