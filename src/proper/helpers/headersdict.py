from .dotdict import DotDict


__all__ = ("HeadersDict",)


class HeadersDict(DotDict):
    """A `proper.Dot` that provides case-insensitive and underscores-to-dashes
    to HTTP request headers.
    """

    def _key_encode(self, key: object) -> str:
        return str(key).title().replace("_", "-")
