from proper import Controller
from proper.concerns import OriginProtection, RateLimiting

from .concerns.form_validation import FormValidation
from .concerns.security_headers import SecurityHeaders


class AppController(
    Controller,
    OriginProtection,
    RateLimiting,
    FormValidation,
    SecurityHeaders,
):
    """All other controllers must inherit from this class.
    """
    pass