import os

from proper.units import MB


env = os.getenv("APP_ENV", "dev")

DEBUG = env == "dev"

if env == "prod":
    PROTOCOL = "https"
    HOST = "YOUR-DOMAIN.com"
else:
    PROTOCOL = "http"
    HOST = "localhost:2300"

# List of secret keys, **oldest to newest**.
# Every key in the list is valid, so you can periodically generate a new key
# and remove the oldest one to add and extra layer of mitigation
# against an attacker discovering a secret key.
if env == "prod":
    SECRET_KEYS = os.getenv("SECRET_KEYS", "").split(",")
else:
    SECRET_KEYS = [
        "---- This is a not-secret-secret_key just for development ----"
    ]

# Turn off to let debugging WSGI middleware handle exceptions.
CATCH_ALL_ERRORS = True

# Limits the total content length (in bytes).
# Raises a RequestEntityTooLarge exception if this value is exceeded.
MAX_CONTENT_LENGTH = 8 * MB

# Limits the content length (in bytes) of the query string.
# Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
MAX_QUERY_SIZE = 1 * MB

STATIC_URL = "/static/"
VIEWS_ASSETS_URL = "/assets/"

# The name of the header to use to return a file
# so the proxy or web-server does it instead of our application.
# Lighttpd uses "X-Sendfile" while NGINX uses "X-/Accel-Redirect"
if env == "prod":
    STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"
else:
    STATIC_X_SENDFILE_HEADER = ""


MAILER = {
    "type": "proper.mail.ToConsoleMailer",
    "default_from": "hello@example.com",
}

if env == "test":
    MAILER["type"] = "proper.mail.ToMemoryMailer"

# if env == "prod":
#     MAILER = {
#         "type": "proper.mail.SMTPMailer",
#         "host": "smtp.example.com",
#         "port": 587,
#         "username": os.getenv("SMTP_USERNAME"),
#         "password": os.getenv("SMTP_PASSWORD"),
#         "use_tls": True,
#         "default_from": MAILER["default_from"],
#     }

update(storage.config)
update(session.config)
