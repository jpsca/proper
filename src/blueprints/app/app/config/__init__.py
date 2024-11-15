import os

from proper import DEV, PROD, env

from .storage import *  # noqa
from .session import *  # noqa


DEBUG: bool = env == DEV

if env == PROD:
    PROTOCOL: str = "https"
    HOST: str = "YOUR-DOMAIN.com"
else:
    PROTOCOL: str = "http"
    HOST: str = "localhost:2300"

# List of secret keys, **OLDEST TO NEWEST**.
# Every key in the list is valid, so you can periodically generate a new key
# and remove the oldest one to add and extra layer of mitigation
# against a improbable discovery of the current secret key
if env == PROD:
    SECRET_KEYS: list[str] = os.getenv("SECRET_KEYS", "").split(",")
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

STATIC_URL = "/static/"
VIEWS_ASSETS_URL = "/static/v/"

# The name of the header to use to return a file
# so the proxy or web-server does it instead of our application.
# Lighttpd uses "X-Sendfile" while NGINX uses "X-/Accel-Redirect"
if env == PROD:
    STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"
else:
    STATIC_X_SENDFILE_HEADER = ""


MAILER_DEFAULT_FROM = "hello@example.com"
