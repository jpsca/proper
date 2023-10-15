from proper import env, DEV, PROD

from .database import *  # noqa
from .scheduler import *  # noqa
from .storage import *  # noqa
from .session import *  # noqa


DEBUG: bool = env == DEV

if env == PROD:
    HOST: str = "https://YOUR-DOMAIN.com"
else:
    HOST: str = "http://127.0.0.1:2300"

# List of secret keys, **OLDEST TO NEWEST**.
# Every key in the list is valid, so you can periodically generate a new key
# and remove the oldest one to add and extra layer of mitigation
# against a improbable discovery of the current secret key
if env == PROD:
    SECRET_KEYS: list[str] = [
        "..."
    ]
else:
    SECRET_KEYS: list[str] = [
        "---- This is a not-secret-secret_key just for development ----"
    ]

# Turn off to let debugging WSGI middleware handle exceptions.
CATCH_ALL_ERRORS: bool = True

# Limits the total content length (in bytes).
# Raises a RequestEntityTooLarge exception if this value is exceeded.
MAX_CONTENT_LENGTH: int = 2**23  # 8 MB

# Limits the content length (in bytes) of the query string.
# Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
MAX_QUERY_SIZE: int = 2**20  # 1 MB

STATIC_HOST: str | None = None
# When set to False then compressed files will not be created but static files
# will still get md5 tagged.

STATIC_COMPRESS: bool = True
# Everything in the `static` folder is available at `/static/...`
# You can add other paths/prefixes here

STATIC_PATHS: list[dict] = [
    # {path: "FOLDER_PATH", prefix: "URL"},
]


MAILER_DEFAULT_FROM = "hello@example.com"
