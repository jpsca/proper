from contextvars import ContextVar

from .helpers import Proxy


_current_app = ContextVar("_current_app", default=None)
_current_request = ContextVar("_current_request", default=None)
_current_response = ContextVar("_current_response", default=None)

app = Proxy(_current_app)
request = Proxy(_current_request)
response = Proxy(_current_response)
