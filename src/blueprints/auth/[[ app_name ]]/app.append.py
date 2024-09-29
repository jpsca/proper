from .auth import Auth

auth = Auth(
    secret_keys=config.SECRET_KEYS,
    hash_name=config.AUTH_HASH_NAME,
    rounds=config.AUTH_ROUNDS,
    password_minlen=config.AUTH_PASSWORD_MINLEN,
    password_maxlen=config.AUTH_PASSWORD_MAXLEN,
)