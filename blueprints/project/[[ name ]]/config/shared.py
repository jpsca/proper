"""
Shared config
"""
import os


debug = False
host = ""

auth = {
    "hash_name": "argon2",
    "rounds": None,
    "password_minlen": 9,
    "password_maxlen": 1024,
    "token_life": 10800,  # 3 hours
}

mailer = {
    "default_from": "admin@jpscaletti.com",
}

session = {
    "cookie_name": "_proper_session",
    "cookie_httponly": True,
}

redis = {
    "host": os.environ.get("REDIS_HOST", "localhost"),
    "port": 6379,
    "db": 0,
}
