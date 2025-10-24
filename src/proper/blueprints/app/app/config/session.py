import os

from proper.units import DAYS


env = os.getenv("APP_ENV", "dev")

SESSION_LIFETIME = 30 * DAYS  # Seconds to expire an unused session.
SESSION_COOKIE_NAME = "_session"
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = (env == "prod")
SESSION_COOKIE_SAMESITE = "Lax"
