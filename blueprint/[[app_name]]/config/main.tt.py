import os

from proper.units import MB


env = os.getenv("APP_ENV", "dev")

DEBUG = env == "dev"


# `HOST`` is the base url of the app, including port if available.
#   Used for generating full URLs
# `PORT`` is used by the server. In production the port will be hidden behind a proxy
#   so it doesn't need to be also specified in the `HOST` variable.
PORT = os.getenv("PORT", 2300)

if env == "prod":
    PROTOCOL = "https"
    HOST = "YOUR-DOMAIN.com"
else:
    PROTOCOL = "http"
    HOST = f"[[ app_name ]].localhost:{PORT}"

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

LOCALE_DEFAULT = "en"
TIMEZONE_DEFAULT = "UTC"

# Turn off to let something else, outside the application,
# like a proxy or web-server, handle the unhandled exceptions.
CATCH_ALL_ERRORS = True

# Limits the total content length (in bytes).
# Raises a RequestEntityTooLarge exception if this value is exceeded.
MAX_CONTENT_LENGTH = 8 * MB

# Limits the content length (in bytes) of the query string.
# Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
MAX_QUERY_SIZE = 1 * MB

# Limits the number of files, fields and the size of each part in a multipart form.
MAX_FORM_FILES = 10
MAX_FORM_FIELDS = 100
MAX_FORM_PART_SIZE = 2 * MB

ASSETS_URL = "/assets/"

# Lets browsers resolve JS package names (like "@hotwired/stimulus") to local or CDN files.
# It allows you to import JS files without needing to process them first with a bundler.
# The values muest be paths relative to `[[ app_name ]]/assets/` or an URL.
IMPORT_MAP = {
    "@hotwired/stimulus": "js/stimulus.js",
    "@hotwired/turbo": "js/turbo.js",
}

# The name of the header to use to return a file
# so the proxy or web-server does it instead of our application.
# Lighttpd uses "X-Sendfile" while NGINX uses "X-/Accel-Redirect"
if env == "prod":
    STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"
else:
    STATIC_X_SENDFILE_HEADER = ""


MAILER = {"type": "proper.emails.ToConsoleMailer"}
MAILER_DEFAULT_OPTIONS = {
    "from": "no-reply@example.com",
}

if env == "test":
    MAILER = {"type": "proper.emails.ToMemoryMailer"}

if env == "prod":
    MAILER = {
        "type": "proper.emails.SMTPMailer",
        "host": "smtp.example.com",
        "port": 587,
        "username": os.getenv("SMTP_USERNAME"),
        "password": os.getenv("SMTP_PASSWORD"),
        "use_tls": True,
    }

