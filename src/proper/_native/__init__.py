"""Proper's native code: `libproper_native.so`, compiled with Free Pascal from
the sources in this directory (`build.py`), loaded with cffi in ABI mode.

What it does now: sign tokens and check them (`Signing`), for `App.dumps`
and `App.loads`.
"""
import threading
import typing as t
from pathlib import Path

from cffi import FFI


__all__ = ("BAD_SIGNATURE", "EXPIRED", "MALFORMED", "Rejected", "Signing", "ffi", "lib")

HERE = Path(__file__).parent
LIBRARY = HERE / "libproper_native.so"
HEADER = HERE / "proper_native.h"

# What `proper_unsign` returns instead of a length
BAD_SIGNATURE = -1
EXPIRED = -2
MALFORMED = -3
TOO_SMALL = -4

# The buffers each thread starts with; a larger token gets larger ones.
BUFFER_SIZE = 64 * 1024


def _load(library: Path = LIBRARY) -> tuple[FFI, t.Any]:
    if not library.exists():
        raise ImportError(
            f"Proper's native library is missing ({library}): "
            "build it with `uv run python src/proper/_native/build.py`"
        )
    ffi = FFI()
    # cffi parses no preprocessor directive
    ffi.cdef("\n".join(
        line for line in HEADER.read_text().splitlines() if not line.startswith("#")
    ))
    return ffi, ffi.dlopen(str(library))


ffi, lib = _load()


class Rejected(Exception):
    """A token `Signing.unsign` refused: `code` says why (`BAD_SIGNATURE`,
    `EXPIRED` or `MALFORMED`)."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class _Buffers(threading.local):
    """The output and scratch buffers of `unsign`, one pair per thread."""

    def __init__(self) -> None:
        self.size = 0
        self.grow(BUFFER_SIZE)

    def grow(self, size: int) -> None:
        self.size = size
        self.out = ffi.new("char[]", size)
        self.scratch = ffi.new("char[]", size)


_buffers = _Buffers()


class Signing:
    """Signs tokens and checks them with HMAC-SHA256 keys of at most 64 bytes,
    prepared once: `keys` oldest first; the newest one signs, and every one
    is tried to check."""

    __slots__ = ("_keys", "_newest", "count")

    def __init__(self, keys: "list[bytes]") -> None:
        size = lib.proper_hmac_key_size()
        self._keys = ffi.new("char[]", size * len(keys))
        for i, key in enumerate(keys):
            if lib.proper_hmac_key(key, len(key), self._keys + i * size) != 0:
                raise ValueError("an HMAC key longer than 64 bytes")
        self._newest = self._keys + (len(keys) - 1) * size
        self.count = len(keys)

    def sign(self, payload: bytes, timestamp: int | None) -> bytes:
        """The token of `payload` (already encoded), timed with `timestamp`
        (Unix seconds) or untimed with `None`."""
        out = ffi.new("char[]", len(payload) + 58)
        n = lib.proper_sign(
            self._newest, payload, len(payload),
            -1 if timestamp is None else timestamp, out, len(payload) + 58,
        )
        return ffi.unpack(out, n)

    def unsign(
        self, token: bytes, *, timed: bool, now: int = 0, max_age: int | None = None
    ) -> tuple[bytes, int]:
        """The payload of a good token (its JSON, decoded from base64 and
        zlib) and its timestamp (0 for an untimed one). Raises `Rejected`
        for any other. `now` is the time in Unix seconds, for `max_age`."""
        timestamp = ffi.new("long long *")
        buffers = _buffers
        while True:
            n = lib.proper_unsign(
                self._keys, self.count, timed, token, len(token), now,
                -1 if max_age is None else max_age, buffers.out, buffers.size,
                buffers.scratch, buffers.size, timestamp,
            )
            if n >= 0:
                return ffi.unpack(buffers.out, n), timestamp[0]
            if n != TOO_SMALL:
                raise Rejected(n)
            buffers.grow(max(buffers.size * 4, len(token)))
