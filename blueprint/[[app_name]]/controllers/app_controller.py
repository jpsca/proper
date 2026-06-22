from proper import Controller
from proper.concerns import OriginProtection, Pagination, RateLimiting

from .concerns.form_validation import FormValidation
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
