from .dot import Dot


__all__ = ("HeadersDict", )


class HeadersDict(Dot):
    """A `proper.Dot` that provides case-insensitive and underscores-to-dashes
    to HTTP request headers.
    """

    def _key_encode(self, key):
        return str(key).title().replace("_", "-")
