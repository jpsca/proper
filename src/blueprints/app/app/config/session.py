from proper import DAYS, PROD, env


SESSION_LIFETIME: int = 30 * DAYS
SESSION_COOKIE_NAME: str = "_session"
SESSION_COOKIE_DOMAIN: str | None = None
SESSION_COOKIE_PATH: str = "/"
SESSION_COOKIE_HTTPONLY: bool = True
SESSION_COOKIE_SECURE: bool = (env == PROD)
SESSION_COOKIE_SAMESITE: t.Literal["Lax"] | t.Literal["Strict"] | None = None
