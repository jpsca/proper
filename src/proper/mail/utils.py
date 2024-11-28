import socket


class CachedDnsName:
    """
    A class to cache the fully qualified domain name (FQDN) of the host.

    This class lazily caches the hostname to avoid the delay caused by
    socket.getfqdn(), which can take a couple of seconds. This is useful
    to speed up operations such as server restarts.
    """

    def __str__(self):
        return self.get_fqdn()

    def get_fqdn(self):
        if not hasattr(self, "_fqdn"):
            self._fqdn = socket.getfqdn()
        return self._fqdn


DNS_NAME = CachedDnsName()

