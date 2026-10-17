"""
The parsers of request bodies: urlencoded forms and query strings,
multipart/form-data, JSON, and the parameters of a header such as
`Content-Type`. Used by `Request`.

The bytes are parsed by the native code (`proper._native`): it gives where
each name, value and file is, and the text is decoded here.
"""
import json
import typing as t
from io import BytesIO
from tempfile import SpooledTemporaryFile

from ... import _native
from ...errors import MultipartError, UriTooLong
from ...helpers import MultiDict, copy_file


# Why the native code refused a multipart body
_MULTIPART_ERRORS = {
    -10: "The multipart body is malformed.",
    -11: "The multipart body ends before the final boundary.",
    -12: "Content-Disposition header is missing.",
    -13: 'The Content-Disposition header field "name" must be provided.',
    -14: "Too many fields. Maximum number of fields is {max_fields}.",
    -15: "Too many files. Maximum number of files is {max_files}.",
    -16: "Field exceeded maximum size of {max_part_size} bytes.",
    -17: "A part of the multipart body has too many headers, or one too long.",
}


def parse_multipart_sync(
    body: bytes,
    options: dict,
    *,
    encoding: str = "utf-8",
    max_files: int = 1000,
    max_fields: int = 1000,
    max_part_size: int = 2 ** 20,
    memfile_limit: int = 2 ** 20,
) -> MultiDict:
    """The fields of a multipart/form-data body: a field as a `str`, a file
    as a `MultipartPart`, whose data is in a `SpooledTemporaryFile` that
    spills to disk past `memfile_limit` bytes.

    The native code frames the body, reads each part's headers and checks
    the limits (`max_fields` and `max_files`, and `max_part_size` bytes for
    a field) before anything is made: a body it refuses is a
    `MultipartError` and leaves no file behind.
    """
    boundary = options.get("boundary", "")
    if not boundary:
        raise MultipartError("No boundary for multipart/form-data.")
    try:
        names, words = _native.parse_multipart(
            body,
            boundary.encode("latin-1"),
            max_fields=max_fields,
            max_files=max_files,
            max_field_size=max_part_size,
        )
    except UnicodeEncodeError:
        raise MultipartError("The multipart boundary is not latin-1.") from None
    except _native.MultipartRejected as rejected:
        raise MultipartError(_MULTIPART_ERRORS[rejected.code].format(
            max_fields=max_fields, max_files=max_files, max_part_size=max_part_size,
        )) from None

    data = memoryview(body)
    form = MultiDict()
    for i in range(0, len(words), _native.PART_WORDS):
        name_at, name_len, file_at, file_len, type_at, type_len, at, size, head_at, head_len = (
            words[i:i + _native.PART_WORDS]
        )
        name = _safe_decode(names[name_at:name_at + name_len], encoding)
        if file_at < 0:
            form.append(name, _safe_decode(data[at:at + size], encoding))
            continue
        part = MultipartPart(encoding=encoding, memfile_limit=memfile_limit)
        part.name = name
        part.filename = _safe_decode(names[file_at:file_at + file_len], encoding)
        if type_at >= 0:
            part.content_type = str(data[type_at:type_at + type_len], "latin-1")
        part._raw_headers = bytes(data[head_at:head_at + head_len])
        part.file = SpooledTemporaryFile(max_size=memfile_limit)
        part.file.write(data[at:at + size])
        part.file.seek(0)
        part.size = size
        form.append(name, part)
    return form


def parse_query_string(query_string: str, *, max_query_size: int | None = None) -> MultiDict:
    """The fields of a query string, as `urllib.parse.parse_qs` reads them
    with `keep_blank_values`: "+" is a space, `%XX` escapes are decoded as
    UTF-8 (U+FFFD where they are not valid), and the characters that are not
    escaped stay as they are."""
    if max_query_size and len(query_string) > max_query_size:
        raise UriTooLong("The query string is too long")
    return _fields(query_string.encode("utf-8"), "utf-8")


def parse_urlencoded(
    body: bytes, encoding: str = "utf-8", *, max_fields: int | None = None
) -> MultiDict:
    """The fields of an `application/x-www-form-urlencoded` body, decoded
    with `encoding`: "+" is a space and `%XX` escapes are decoded (U+FFFD
    where they are not valid in `encoding`). The body itself must be valid
    in `encoding`: `Request` checks it first. More than `max_fields` fields
    is a `MultipartError` (400)."""
    try:
        return _fields(body, encoding, max_fields)
    except _native.TooManyFields:
        raise MultipartError(
            _MULTIPART_ERRORS[-14].format(max_fields=max_fields)
        ) from None


def _fields(data: bytes, encoding: str, max_fields: int | None = None) -> MultiDict:
    form = MultiDict()
    if not data:
        return form
    text, words = _native.parse_form(data, max_fields)
    for name, name_len, value, value_len in zip(
        words[0::4], words[1::4], words[2::4], words[3::4], strict=True
    ):
        form.append(
            str(text[name:name + name_len], encoding, "replace"),
            str(text[value:value + value_len], encoding, "replace"),
        )
    return form


def parse_json(content: str, *, strict: bool = True) -> MultiDict:
    """Parse a JSON body into a MultiDict.

    The members of a JSON object are the fields. Any other JSON value (an
    array, a string, a number, `true`, `false` or `null`) gives an empty
    `MultiDict`.

    A body that `json` cannot read is a `MultipartError` (400): invalid
    JSON, an integer with more digits than Python converts (4300 by
    default, a `ValueError`), or arrays and objects nested deeper than the
    interpreter's stack allows (a `RecursionError`).
    """
    form = MultiDict()
    try:
        data = json.loads(content)
    except (ValueError, RecursionError) as err:
        # `json.JSONDecodeError` is a `ValueError`.
        if strict:
            raise MultipartError(str(err)) from None
        return form

    if isinstance(data, dict):
        form.update(data)
    return form


def parse_options_header(
    header: str,
    options: dict[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Parse a Content-Type style header into a content-type and options dict.

    As python-multipart reads it: `;` inside quotes doesn't split, values
    are unquoted, and the extended syntax of RFC 2231 (`filename*=`) is
    ignored, as RFC 7578 says for multipart/form-data. The content-type
    and the parameter names are lowercased, because they are
    case-insensitive (RFC 9110 §8.3.1); the parameter values keep their
    case.

    >>> head = 'form-data; name="Test"; '
    >>> parse_options_header(head + 'filename="Test.txt"')[0]
    'form-data'
    >>> parse_options_header(head + 'filename="Test.txt"')[1]['name']
    'Test'

    """
    if not header:
        return "", {}
    result: dict[str, str] = options or {}
    if ";" not in header:
        return header.strip().lower(), result
    try:
        data = header.encode("latin-1")
    except UnicodeEncodeError:
        data = header.encode("utf-8")
    params = _native.parse_params(data)
    for key, value in params[1:]:
        result[key.decode("latin-1")] = value.decode("latin-1")
    return params[0][0].decode("latin-1").strip().lower(), result


def _safe_decode(src: t.Any, codec: str) -> str:
    """Decode bytes (or a memoryview), falling back to latin-1 on errors."""
    try:
        return str(src, codec)
    # `ValueError` (which `UnicodeDecodeError` is) for a codec name that
    # can't be looked up at all, such as one with a NUL.
    except ValueError, LookupError:
        return str(src, "latin-1")


# --- MultipartPart ---


class MultipartPart:
    """A single part of a multipart/form-data upload.

    Attributes:
        name:
            The field name from the Content-Disposition header.
        filename:
            The filename from the Content-Disposition header, or None
            for non-file fields.
        file:
            A file-like object containing the part's data.  For small
            fields this is a `BytesIO`; for larger uploads it is a
            `SpooledTemporaryFile` that may spill to disk.
        content_type:
            The Content-Type of this part, or None.
        size:
            Number of data bytes written so far.
        headers:
            The raw headers of this part as a list of (name, value) tuples,
            the names in lowercase.

    """

    def __init__(
        self,
        *,
        encoding: str = "utf-8",
        memfile_limit: int = 2 ** 20,
    ):
        self.name: str = ""
        self.filename: str | None = None
        self.file: t.IO[bytes] | None = None
        self.content_type: str | None = None
        self.encoding: str = encoding
        self.size: int = 0
        self.memfile_limit = memfile_limit
        self._raw_headers = b""
        self._headers: list[tuple[bytes, bytes]] | None = None

    @property
    def headers(self) -> list[tuple[bytes, bytes]]:
        """Read from the part's raw headers the first time they are asked for."""
        if self._headers is None:
            self._headers = []
            # each line ends with CRLF; the block has no empty line
            for line in self._raw_headers.split(b"\r\n"):
                if line:
                    name, _, value = line.partition(b":")
                    self._headers.append((name.lower(), value.lstrip(b" ")))
        return self._headers

    @headers.setter
    def headers(self, value: list[tuple[bytes, bytes]]) -> None:
        self._headers = value

    def is_buffered(self) -> bool:
        """Return True if the data is fully buffered in memory."""
        return isinstance(self.file, BytesIO)

    @property
    def value(self) -> str:
        """Data decoded with the specified charset."""
        return self.raw.decode(self.encoding)

    @property
    def raw(self) -> bytes:
        """Data without decoding."""
        if not self.file:
            return b""

        pos = self.file.tell()
        self.file.seek(0)
        try:
            return self.file.read()
        finally:
            self.file.seek(pos)

    def save_as(self, path: str) -> int:
        assert self.file
        with open(path, "wb") as fp:
            pos = self.file.tell()
            try:
                self.file.seek(0)
                return copy_file(self.file, fp)
            finally:
                self.file.seek(pos)

    def close(self):
        if self.file:
            self.file.close()
            self.file = None
