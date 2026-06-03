from typing import Final


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
