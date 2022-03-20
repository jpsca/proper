import multipart

from proper import errors
from proper.helpers import MultiDict


__all__ = ("parse_query_string",)


def parse_query_string(query_string, max_query_size=None):
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
        return _parse_query_string(query_string, max_query_size)
    except ValueError:
        raise errors.BadRequest()


def _parse_query_string(query_string, max_query_size=None):
    query = MultiDict()
    if not query_string:
        return query

    if max_query_size and len(query_string) > max_query_size:
        raise errors.UriTooLong("The query string is too long")

    data = multipart.parse_qs(query_string, keep_blank_values=True)
    for key, values in data.items():
        query[key] = [True if value == "" else value for value in values]
    return query
