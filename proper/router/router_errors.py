"""
## proper_router.router_errors

"""
from ..errors import MatchNotFound  # noqa
from ..errors import MethodNotAllowed  # noqa


class MissingParameter(Exception):
    pass


class BadParameter(Exception):
    pass


class BadRule(Exception):
    pass


class NameNotFound(Exception):
    pass
