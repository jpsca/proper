"""
## proper.support.headersdict

"""
from .dot import Dot


__all__ = ("HeadersDict",)


class HeadersDict(Dot):
    """A `proper.Dot` that provides case-insensitive and dahses-to-underscores
    to HTTP request headers.
    """

    def _key_encode(self, key):
        return str(key).upper().replace("-", "_")
