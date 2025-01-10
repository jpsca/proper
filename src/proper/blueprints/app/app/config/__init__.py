import os

from proper import DEV, MB, PROD, TEST, Config, env

from . import session, storage


config = Config()

config.DEBUG = env == DEV

if env == PROD:
    config.PROTOCOL = "https"
    config.HOST = "YOUR-DOMAIN.com"
else:
    config.PROTOCOL = "http"
    config.HOST = "localhost:2300"

# List of secret keys, **oldest to newest**.
# Every key in the list is valid, so you can periodically generate a new key
# and remove the oldest one to add and extra layer of mitigation
# against an attacker discovering a secret key.
if env == PROD:
    config.SECRET_KEYS = os.getenv("SECRET_KEYS", "").split(",")
else:
    config.SECRET_KEYS = [
        "---- This is a not-secret-secret_key just for development ----"
    ]

# Turn off to let debugging WSGI middleware handle exceptions.
config.CATCH_ALL_ERRORS = True

# Limits the total content length (in bytes).
# Raises a RequestEntityTooLarge exception if this value is exceeded.
config.MAX_CONTENT_LENGTH = 8 * MB

# Limits the content length (in bytes) of the query string.
# Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
config.MAX_QUERY_SIZE = 1 * MB

config.STATIC_URL = "/static/"
config.VIEWS_ASSETS_URL = "/static/v/"

# The name of the header to use to return a file
# so the proxy or web-server does it instead of our application.
# Lighttpd uses "X-Sendfile" while NGINX uses "X-/Accel-Redirect"
if env == PROD:
    config.STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"
else:
    config.STATIC_X_SENDFILE_HEADER = ""


config.MAILER = {
    "type": "proper.mail.ToConsoleMailer",
    "default_from": "hello@example.com",
}

if env == TEST:
    config.MAILER["type"] = "proper.mail.ToMemoryMailer"

# if env == PROD:
#     config.MAILER = {
#         "type": "proper.mail.SMTPMailer",
#         "host": "smtp.example.com",
#         "port": 587,
#         "username": os.getenv("SMTP_USERNAME"),
#         "password": os.getenv("SMTP_PASSWORD"),
#         "use_tls": True,
#         "default_from": config.MAILER["default_from"],
#     }


config.update(storage.config)
config.update(session.config)
