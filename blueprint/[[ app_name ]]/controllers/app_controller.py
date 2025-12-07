from proper import Controller
from proper.concerns import (
    RateLimiting,
    RequestForgeryProtection,
)

from .concerns.security_headers import SetSecurityHeaders


class AppController(
    Controller,
    RateLimiting,
    RequestForgeryProtection,
    SetSecurityHeaders,
):
    """All other controllers must inherit from this class.
    """
    pass