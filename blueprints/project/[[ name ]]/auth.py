from proper.auth import AuthManager

from .app import config


auth = AuthManager(
    hash_name=config.auth.hash_name,
    rounds=config.auth.rounds,
    password_minlen=config.auth.password_minlen,
    password_maxlen=config.auth.password_maxlen,
)
