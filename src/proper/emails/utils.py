import socket
import typing as t
from collections.abc import Iterable


def punycode(domain: str) -> str:
    """Return the Punycode of the given domain if it's non-ASCII."""
    return domain.encode("idna").decode("ascii")


def force_str(s: t.Any, encoding="utf-8", strings_only=False, errors="strict"):
    """
    Force a string to be the native type.

    Args:
        s: The string or bytes to be converted.
        encoding: The encoding to use if `s` is bytes. Defaults to "utf-8".
        errors: The error handling scheme to use for encoding errors. Defaults to "strict".

    Returns:
        The converted string.

    """
    if isinstance(s, str):
        return s
    if strings_only and not isinstance(s, bytes):
        return s
    return str(s, encoding, errors)


def force_bytes(s: t.Any, encoding="utf-8", strings_only=False, errors="strict"):
    """
    Similar to smart_bytes, except that lazy instances are resolved to
    strings, rather than kept as lazy objects.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    # Handle the common case first for performance reasons.
    if isinstance(s, bytes):
        if encoding == "utf-8":
            return s
        else:
            return s.decode("utf-8", errors).encode(encoding, errors)
    if strings_only:
        return s
    if isinstance(s, memoryview):
        return bytes(s)
    return str(s).encode(encoding, errors)


def to_list(value: Iterable[str] | None) -> list[str]:
    """
    Convert a sequence or `None` to a list.

    Args:
        value: The input value to convert.

    Returns:
        A list. If the input is None, returns an empty list.

    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


class CachedDnsName:
    """Cache the hostname, but do it lazily: socket.getfqdn() can take a couple of
    seconds, which slows down the restart of the server."""
    def __str__(self):
        return self.get_fqdn()

    def get_fqdn(self):
        if not hasattr(self, "_fqdn"):
            self._fqdn = punycode(socket.getfqdn())
        return self._fqdn


DNS_NAME = CachedDnsName()
