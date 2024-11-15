from proper import HOURS, Config


config = Config()

config.AUTH_HASH_NAME = "argon2"
config.AUTH_ROUNDS = None  # =default
config.AUTH_PASSWORD_MINLEN = 9
config.AUTH_PASSWORD_MAXLEN = 1024
config.AUTH_TOKEN_LIFE = 3 * HOURS
