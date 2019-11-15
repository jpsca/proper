"""
## proper.parsers.parse_host

"""
__all__ = ("parse_host", )


def parse_host(host):
    """Parse a host string.

    It may or may not contain a port, be and IPv4 address, or be
    an IPv6 address.

    Arguments are:

        host (header):
            The value of the HTTP_HOST header

    Returns (str):

        The parsed host or an empty string.

    """
    if not host:
        return ""

    if host.startswith("["):  # IPv6
        pos = host.rfind("]:")
        if pos != -1:
            return host[1:pos]
        else:
            return host[1:-1]

    pos = host.rfind(":")
    if (pos == -1) or (pos != host.find(":")):
        # IP address or a host name
        return host

    return host.split(":")[0]
