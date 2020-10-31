"""
When a request comes in, web servers decode some fields like the path.
The decoded path may contain UTF-8 characters but, according to the WSGI spec,
no strings can contain chars outside ISO-8859-1.

To reconcile the URI encoding standard that allows UTF-8 with the WSGI spec
that does not, WSGI servers tunnel the string via ISO-8859-1. Theses functions
does that:

    >>> tunnel_encode('olé')
    'olÃ©'

    >>> tunnel_decode('olÃ©')
    'olé'

"""
__all__ = ("tunnel_encode", "tunnel_decode", )


def tunnel_encode(string, charset="utf8"):
    return string.encode(charset).decode("iso-8859-1")


def tunnel_decode(string, charset="utf8"):
    return string.encode("iso-8859-1").decode(charset, "replace")
