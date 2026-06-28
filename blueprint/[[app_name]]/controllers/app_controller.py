from proper import Controller
from proper.concerns import FormValidation, OriginProtection, Pagination, RateLimiting

from .concerns.security_headers import SecurityHeaders


class AppController(
    OriginProtection,
    Pagination,
    RateLimiting,
    FormValidation,
    SecurityHeaders,
    Controller,
):
    """All other controllers must inherit from this class.
    """
    pass
