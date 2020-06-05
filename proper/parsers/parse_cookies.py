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
    parsed = {}
    for pair in cookie.split("; "):
        try:
            name, value = pair.split("=", 1)
            parsed[name] = value
        except ValueError:
            pass
    return parsed
