"""
## proper.parsers.parse_cookies

"""
__all__ = ("parse_cookies",)


def parse_cookies(cookie):
    """Parse a cookie header into a dict.

    Arguments are:

        cookie (str):
            The value of the HTTP_COOKIE header.

    Returns (dict)

    """
    if not cookie:
        return {}
    cookie = cookie.strip(";")
    return dict([pair.split("=", 1) for pair in cookie.split("; ")])
