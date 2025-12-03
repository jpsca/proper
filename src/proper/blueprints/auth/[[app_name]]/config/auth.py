from proper.units import HOURS


AUTH_HASH_NAME = "argon2"
AUTH_ROUNDS = None  # `None` means using the default number for the hash"
AUTH_PASSWORD_MINLEN = 9
AUTH_PASSWORD_MAXLEN = 1024
# Number of seconds before a reset-password token expires
AUTH_TOKEN_LIFE = 3 * HOURS
