from datetime import timedelta

from proper import DotDict

from .database import database_config
from .redis import redis_config
from .scheduler import scheduler_config


config = DotDict()

config.debug = False
config.host = "http://127.0.0.1:2300"

# Used for verifying the integrity of signed cookies, signed URLs, etc.
# Every key in the list is valid, so you can generate a new key and
# remove the oldest key periodically to add and extra layer of mitigation
# against an attacker discovering a secret key
config.secret_keys = []

# Turn off to let debugging middleware handle exceptions.
config.catch_all_errors = True

# Limits the total content length (in bytes).
# Raises a RequestEntityTooLarge exception if this value is exceeded.
config.max_content_length = 2**23  # 8 MB

# Limits the content length (in bytes) of the query string.
# Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
config.max_query_size = 2**20  # 1 MB

config.session = DotDict()
config.session.lifetime = timedelta(days=30).total_seconds()

config.session.cookie = DotDict()
config.session.cookie.name = "_session"
config.session.cookie.domain = None
config.session.cookie.path = "/"
config.session.cookie.httponly = True
config.session.cookie.secure = False
config.session.cookie.samesite = None  # "Lax", "Strict", or None

config.static = DotDict()
config.static.host = None

# When set to False then compressed files will not be created but static files
# will still get md5 tagged.
config.static.compress = True

config.static.paths = [
    # Everything in the `static` folder is available at `/static/...`
    # You can add other paths/prefixes here
    # {"path": "FOLDER_PATH", "prefix": "URL"},
]

config.mailer = DotDict()
config.mailer.default_from = "hello@example.com"

config.database = database_config
config.redis = redis_config
config.scheduler = scheduler_config
