from proper import HOURS


AUTH_HASH_NAME: str = "argon2"
AUTH_ROUNDS: int | None = None  # default
AUTH_PASSWORD_MINLEN: int = 9
AUTH_PASSWORD_MAXLEN: int = 1024
AUTH_TOKEN_LIFE: int = 3 * HOURS

