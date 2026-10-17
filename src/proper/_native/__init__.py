"""Proper's native code: `libproper_native.so`, compiled with Free Pascal from
the sources in this directory (`build.py`), loaded with cffi in ABI mode.

What it does now: sign tokens and check them (`Signing`), for `App.dumps`
and `App.loads`; parse request bodies and headers (`parse_form`,
`parse_params`, `parse_multipart`), for `proper.core.request.formparser`;
and turn HTML into plain text (`html2text`), for `proper.helpers.html2text`.
"""
import threading
import typing as t
from pathlib import Path

from cffi import FFI


__all__ = (
    "BAD_SIGNATURE", "EXPIRED", "MALFORMED", "Rejected", "Signing", "ffi", "html2text",
    "lib", "parse_form", "parse_multipart", "parse_params",
)

HERE = Path(__file__).parent
LIBRARY = HERE / "libproper_native.so"
HEADER = HERE / "proper_native.h"

# What `proper_unsign` returns instead of a length
BAD_SIGNATURE = -1
EXPIRED = -2
MALFORMED = -3
TOO_SMALL = -4

# The buffers each thread starts with; a larger token or body gets larger ones.
BUFFER_SIZE = 64 * 1024
# Records each thread starts with: the parts of a multipart body, the
# parameters of one header, and the links open at once in an HTML.
PARTS = 64
PARAMS = 64
LINKS = 64
# Words per record
FIELD_WORDS = 4
PARAM_WORDS = 4
PART_WORDS = 10
NAME_WORDS = 4
LINK_WORDS = 3


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
    """The output and scratch buffers of `sign_json` and `unsign`, and the
    deflate stream of `sign_json`, one of each per thread. The stream is
    made once and reset for each token: making one costs more than
    compressing a cookie. Its memory is zlib's; `deflateEnd` frees it when
    the thread is gone."""

    def __init__(self) -> None:
        self.size = 0
        self.grow(BUFFER_SIZE)
        stream = ffi.new("char[]", lib.proper_deflate_size())
        if lib.proper_deflate_init(stream) != 0:  # pragma: no cover
            raise RuntimeError("zlib could not make a deflate stream (is libz.so.1 there?)")
        self.stream = ffi.gc(stream, lib.proper_deflate_end)

        self.parts = PARTS
        self.part_records = ffi.new("long long[]", PARTS * PART_WORDS)
        self.params = PARAMS
        self.param_records = ffi.new("long long[]", PARAMS * PARAM_WORDS)
        self.links = LINKS
        self.link_records = ffi.new("long long[]", LINKS * LINK_WORDS)

    def grow(self, size: int) -> None:
        self.size = size
        self.out = ffi.new("char[]", size)
        self.scratch = ffi.new("char[]", size)

    def grow_records(self) -> None:
        self.parts *= 4
        self.part_records = ffi.new("long long[]", self.parts * PART_WORDS)
        self.params *= 4
        self.param_records = ffi.new("long long[]", self.params * PARAM_WORDS)
        self.links *= 4
        self.link_records = ffi.new("long long[]", self.links * LINK_WORDS)


_buffers = _Buffers()


class Signing:
    """Signs tokens and checks them for one salt. `secret_keys` go oldest
    first: the newest one signs, and every one is tried to check. The signing
    key of each is derived once, as itsdangerous derives it: the HMAC-SHA256
    of the salt keyed with the secret key."""

    __slots__ = ("_keys", "_newest", "count")

    def __init__(self, secret_keys: "list[bytes]", salt: bytes) -> None:
        size = lib.proper_hmac_key_size()
        self._keys = ffi.new("char[]", size * len(secret_keys))
        for i, secret in enumerate(secret_keys):
            lib.proper_derive_key(secret, len(secret), salt, len(salt), self._keys + i * size)
        self._newest = self._keys + (len(secret_keys) - 1) * size
        self.count = len(secret_keys)

    def sign_json(self, json: bytes, timestamp: int | None) -> bytes:
        """The token of a JSON text (compressed with zlib when that makes it
        shorter), timed with `timestamp` (Unix seconds) or untimed with
        `None`, signed with the newest key."""
        buffers = _buffers
        while True:
            n = lib.proper_sign_json(
                self._newest, buffers.stream, json, len(json),
                -1 if timestamp is None else timestamp, buffers.out, buffers.size,
                buffers.scratch, buffers.size,
            )
            if n >= 0:
                return ffi.unpack(buffers.out, n)
            buffers.grow(max(buffers.size * 4, len(json) * 2 + 128))

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


def parse_form(data: bytes, max_fields: int | None = None) -> "tuple[memoryview, list[int]]":
    """The fields of an urlencoded body or query string: the decoded bytes,
    and a name offset, name length, value offset and value length for each
    field, in order. The bytes are this thread's buffer: decode them before
    the next call. Raises `TooManyFields` for more than `max_fields`."""
    fields = data.count(b"&") + 1
    if max_fields is not None:
        fields = min(fields, max_fields)
    records = ffi.new("long long[]", fields * FIELD_WORDS)
    buffers = _buffers
    if buffers.size < len(data):
        buffers.grow(max(buffers.size * 4, len(data)))
    n = lib.proper_parse_form(data, len(data), buffers.out, buffers.size, records, fields)
    if n < 0:
        raise TooManyFields(n)
    return memoryview(ffi.buffer(buffers.out, len(data))), ffi.unpack(records, n * FIELD_WORDS)


def parse_params(value: bytes) -> "list[tuple[bytes, bytes]]":
    """The type and parameters of a header value (latin-1), as
    `(key, value)`: the type first, with an empty value."""
    buffers = _buffers
    while True:
        if buffers.size < 3 * len(value) + 16:
            buffers.grow(max(buffers.size * 4, 3 * len(value) + 16))
        n = lib.proper_parse_params(
            value, len(value), buffers.out, buffers.size,
            buffers.param_records, buffers.params,
        )
        if n >= 0:
            break
        buffers.grow_records()
    out = ffi.buffer(buffers.out, buffers.size)
    words = ffi.unpack(buffers.param_records, n * PARAM_WORDS)
    return [
        (out[k:k + kl], out[v:v + vl])
        for k, kl, v, vl in zip(words[0::4], words[1::4], words[2::4], words[3::4], strict=True)
    ]


class TooManyFields(Exception):
    """An urlencoded body with more fields than `parse_form` may read."""


class MultipartRejected(Exception):
    """A multipart body `parse_multipart` refused: `code` says why."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def parse_multipart(
    body: bytes, boundary: bytes, *, max_fields: int, max_files: int, max_field_size: int
) -> "tuple[bytes, list[int]]":
    """The parts of a multipart/form-data body: the names and filenames, as
    bytes, and for each part the offset and length of its name and filename
    (-1 for a field) in them, and of its content-type (-1 without one), data
    and headers in `body`. Raises `MultipartRejected`."""
    buffers = _buffers
    while True:
        n = lib.proper_parse_multipart(
            body, len(body), boundary, len(boundary), buffers.out, buffers.size,
            buffers.part_records, buffers.parts, max_fields, max_files, max_field_size,
            buffers.param_records, buffers.params,
        )
        if n >= 0:
            break
        if n != TOO_SMALL:
            raise MultipartRejected(n)
        buffers.grow(buffers.size * 4)
        buffers.grow_records()
    words = ffi.unpack(buffers.part_records, n * PART_WORDS)
    # a copy of the names and filenames: the buffer is this thread's
    end = 0
    for i in range(0, len(words), PART_WORDS):
        end = max(end, words[i] + words[i + 1], words[i + 2] + words[i + 3])
    return ffi.buffer(buffers.out, end)[:], words


def html2text(html: bytes, filenames: "dict[bytes, bytes]") -> bytes:
    """The plain text of an HTML (UTF-8), as `proper_text.pas` describes it.
    `filenames`: the filename of each attachment, by its sgid."""
    names = b"".join(sgid + name for sgid, name in filenames.items())
    records = []
    at = 0
    for sgid, name in filenames.items():
        records += [at, len(sgid), at + len(sgid), len(name)]
        at += len(sgid) + len(name)
    name_records = ffi.new("long long[]", records) if records else ffi.NULL
    buffers = _buffers
    # The text is at most a few times the HTML (an "<hr>" is 20 "-")
    need = 2 * len(html) + len(names) + 256
    if buffers.size < need:
        buffers.grow(max(buffers.size * 4, need))
    while True:
        n = lib.proper_html2text(
            html, len(html), names, name_records, len(filenames), buffers.out, buffers.size,
            buffers.scratch, buffers.size, buffers.link_records, buffers.links,
        )
        if n >= 0:
            return ffi.unpack(buffers.out, n)
        buffers.grow(buffers.size * 4)
        buffers.grow_records()
