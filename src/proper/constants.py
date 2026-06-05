from typing import Final


DB_QUEUE = "proper_queue"
DB_CACHE = "proper_cache"

# HTTP methods (minus CONNECT and TRACE)
GET: Final = "GET"
HEAD: Final = "HEAD"
POST: Final = "POST"
PUT: Final = "PUT"
DELETE: Final = "DELETE"
OPTIONS: Final = "OPTIONS"
PATCH: Final = "PATCH"
QUERY: Final = "QUERY"

# RESTful actions
ACTION_INDEX = "index"
ACTION_NEW = "new"
ACTION_CREATE = "create"
ACTION_SHOW = "show"
ACTION_EDIT = "edit"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"

FLASHES_SESSION_KEY: Final = "_flashes"

# Default salt for signed cookies
SIGNED_COOKIE_SALT: Final = "cookie"

SESSION_COOKIE_NAME = "_session"
SESSION_COOKIE_SALT = "session cookie"
AUTH_COOKIE_NAME: Final = "_auth"
AUTH_COOKIE_SALT: Final = "auth cookie"
