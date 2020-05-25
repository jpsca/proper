from ..errors import MatchNotFound, MethodNotAllowed  # noqa


class MissingParameter(Exception):
    pass


class BadParameter(Exception):
    pass


class BadRule(Exception):
    pass


class NameNotFound(Exception):
    pass
