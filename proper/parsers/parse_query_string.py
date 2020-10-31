import multipart

from .. import errors
from ..helpers import MultiDict


__all__ = ("parse_query_string",)


def parse_query_string(query_string, config=None):
    """Parse a query string into a MultiDict.

    Query string parameters are assumed to use standard form-encoding.

    Arguments are:

        query_string (str):
            The value of the HTTP_QUERY_STRING header.

    Returns (MultiDict):

        A MultiDict of `name: [value1, value2, ...]` pairs.
        Like with all MultiDict, the *values* are always a list, even when
        only one is found for that key.

    """
    try:
        return _parse_query_string(query_string, config)
    except ValueError:
        raise errors.BadRequest()


def _parse_query_string(query_string, config):
    query = MultiDict()
    if not query_string:
        return query

    config = config or {}
    max_query_size = config.get("max_query_size")
    if max_query_size and len(query_string) > max_query_size:
        raise errors.UriTooLong("The query string is too long")

    data = multipart.parse_qs(query_string, keep_blank_values=True)
    for key, values in data.items():
        query[key] = [True if value == "" else value for value in values]
    return query
