from proper import HOURS, Config, get_env


config = Config()
env = get_env()

config.AUTH_HASH_NAME = "argon2"
# `None` means using the default number for the hash".
config.AUTH_ROUNDS = None
config.AUTH_PASSWORD_MINLEN = 9
config.AUTH_PASSWORD_MAXLEN = 1024
# Number of seconds before a reset-password token expires
config.AUTH_TOKEN_LIFE = 3 * HOURS
