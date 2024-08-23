"""
Extracted from Django (http://djangoproject.com).
The original code was BSD licensed (see LICENSE)
"""
import socket


class CachedDnsName:
    """Cache the hostname, but do it lazily: socket.getfqdn() can take a
    couple of seconds, which slows down the restart of the server.
    """

    def __str__(self):
        return self.get_fqdn()

    def get_fqdn(self):
        if not hasattr(self, "_fqdn"):
            self._fqdn = socket.getfqdn()
        return self._fqdn


DNS_NAME = CachedDnsName()


def force_str(s, encoding="utf-8", errors="strict"):
    """Force a string to be the native text_type"""
    if isinstance(s, str):
        return s
    return str(s, encoding, errors)
