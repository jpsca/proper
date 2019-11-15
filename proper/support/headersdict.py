"""
## proper.support.headersdict

"""
from .dot import Dot


__all__ = ("HeadersDict",)


class HeadersDict(Dot):
    """A `proper.Dot` that provides case-insensitive and underscores-for-dashes
    to HTTP request headers.
    """

    def _key_encode(self, key):
        return str(key).lower().replace("_", "-")
