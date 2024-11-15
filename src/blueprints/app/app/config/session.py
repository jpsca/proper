from proper import DAYS, PROD, Config, env


config = Config()

# Number of seconds before a non-used session key expires.
config.SESSION_LIFETIME = 30 * DAYS
config.SESSION_COOKIE_NAME = "_session"
config.SESSION_COOKIE_DOMAIN = None
config.SESSION_COOKIE_PATH = "/"
config.SESSION_COOKIE_HTTPONLY = True
config.SESSION_COOKIE_SECURE = (env == PROD)
config.SESSION_COOKIE_SAMESITE = "Lax"
