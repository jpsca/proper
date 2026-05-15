from proper.units import DAYS


SESSION_COOKIE_LIFETIME = 30 * DAYS  # Seconds to expire an unused session.
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
