from datetime import timedelta

from proper import Dot

from .database import config as database_config


config = Dot()

config.debug = False
config.host = None

# Used for verifying the integrity of signed cookies
config.secret_key = ""

# Turn off to let debugging middleware handle exceptions.
config.catch_all_errors = True

# Limits the total content length (in bytes).
# Raises a RequestEntityTooLarge exception if this value is exceeded.
config.max_content_length = 2 ** 23  # 8 MB

# Limits the content length (in bytes) of the query string.
# Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
config.max_query_size = 2 ** 20  # 1 MB

config.session = Dot()
config.session.lifetime = timedelta(days=30).total_seconds()

config.session.cookie = Dot()
config.session.cookie.name = "_session"
config.session.cookie.domain = None
config.session.cookie.path = "/"
config.session.cookie.httponly = True
config.session.cookie.secure = False
config.session.cookie.samesite = None  # "Lax", "Strict", or None

config.static = Dot()
config.static.host = None

# When set to False then compressed files will not be created but static files
# will still get md5 tagged.
config.static.compress = True

config.static.paths = [
    # Everything in the `static` folder is available at `/static/...`
    # You can add other paths/prefixes here
    # {"path": "FOLDER_PATH", "prefix": "URL"},
]

config.auth = Dot()
config.auth.hash_name = "argon2"
config.auth.rounds = None  # default
config.auth.password_minlen = 9
config.auth.password_maxlen = 1024
config.auth.token_life = 10800  # 3 hours

config.mailer = Dot()
config.mailer.default_from = "hello@example.com"

config.database = database_config
