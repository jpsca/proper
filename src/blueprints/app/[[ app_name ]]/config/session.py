from datetime import timedelta

from proper import PROD, env


SESSION_LIFETIME: int = int(timedelta(days=30).total_seconds())
SESSION_COOKIE_NAME: str = "_session"
SESSION_COOKIE_DOMAIN: str | None = None
SESSION_COOKIE_PATH: str = "/"
SESSION_COOKIE_HTTPONLY: bool = True
SESSION_COOKIE_SECURE: bool = env == PROD
# "Lax", "Strict", or None
SESSION_COOKIE_SAMESITE: bool = False
