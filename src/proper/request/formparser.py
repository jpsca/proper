"""
Multipart/form-data parser using python-multipart.
Uses an async stream interface compatible with ASGI.
"""
# Adapted and extened from Starlette's `formparsers.py`,
# which is licensed under the BSD 3-Clause License.
# ---- START OF LICENSE ---
# Copyright © 2018, Encode OSS Ltd. All rights reserved.
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this list
# of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions and the following disclaimer in the documentation and/or other
# materials provided with the distribution.
#
# Neither the name of the copyright holder nor the names of its contributors may be
# used to endorse or promote products derived from this software without specific
# prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.
# ---- END OF LICENSE ---
import json
import typing as t
from collections.abc import AsyncGenerator
from io import BytesIO
from tempfile import SpooledTemporaryFile
from urllib.parse import parse_qs

import python_multipart as multipart
from python_multipart.multipart import parse_options_header as _pm_parse_options_header

from ..errors import MultipartError, UriTooLong
from ..helpers import MultiDict


T = t.TypeVar("T")


class _AwaitableForm:
    """Wraps a coroutine so it can be used as both ``await`` and ``async with``.

    Usage::

        # Just await it:
        form = await request.form()

        # Or use as a context manager that auto-closes file parts:
        async with request.form() as form:
            ...
    """

    __slots__ = ("_coro", "_result")

    def __init__(self, coro: t.Coroutine[t.Any, t.Any, MultiDict]) -> None:
        self._coro = coro
        self._result: MultiDict | None = None

    def __await__(self) -> t.Generator[t.Any, None, MultiDict]:
        return self._coro.__await__()

    async def __aenter__(self) -> MultiDict:
        self._result = await self._coro
        return self._result

    async def __aexit__(self, *args: t.Any) -> None:
        if self._result is not None:
            for values in self._result.data.values():
                for value in values:
                    if isinstance(value, MultipartPart):
                        value.close()
            self._result = None


async def parse_multipart(
    stream: AsyncGenerator[bytes, None],
    options: dict,
    *,
    encoding: str = "utf-8",
    max_files: int = 1000,
    max_fields: int = 1000,
    max_part_size: int = 2 ** 20,
    memfile_limit: int = 2 ** 20,
) -> MultiDict:
    """Parse a multipart/form-data async stream into a MultiDict.

    Non-file fields are stored as strings.  File fields are stored as
    ``MultipartPart`` instances (with a ``.file`` attribute).
    """
    boundary = options.get("boundary", "")
    if not boundary:
        raise MultipartError("No boundary for multipart/form-data.")

    parser = MultipartParser(
        stream,
        boundary,
        encoding=encoding,
        max_files=max_files,
        max_fields=max_fields,
        max_part_size=max_part_size,
        memfile_limit=memfile_limit,
    )

    items = await parser.parse()
    form = MultiDict()
    for name, value in items:
        form.append(name, value)
    return form


def parse_query_string(
    query_string: str,
    *,
    encoding: str = "utf8",
    max_query_size: int | None = None,
    strict: bool = True,
) -> MultiDict:
    if max_query_size and len(query_string) > max_query_size:
        raise UriTooLong("The query string is too long")

    form = MultiDict()
    try:
        data = parse_qs(query_string, keep_blank_values=True, encoding=encoding)
        for key, values in data.items():
            form.extend(key, values)
    except ValueError:  # pragma: no cover
        if strict:
            raise

    return form


def parse_json(content: str, *, strict: bool = True) -> MultiDict:
    form = MultiDict()
    try:
        data = json.loads(content)
        form.update(data)
    except json.JSONDecodeError as err:
        if strict:
            raise MultipartError(str(err)) from None

    return form


def copy_file(
    stream: t.IO[bytes],
    target: t.IO[bytes],
    maxread: int = -1,
    buffer_size: int = 2 ** 16,
) -> int:
    """Read from *stream* and write to *target* until *maxread* or EOF."""
    size, read = 0, stream.read

    while True:
        to_read = buffer_size if maxread < 0 else min(buffer_size, maxread - size)
        part = read(to_read)

        if not part:
            return size

        target.write(part)
        size += len(part)


def parse_options_header(
    header: str,
    options: dict[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Parse a Content-Type style header into a content-type and options dict.

    Uses python-multipart's parser internally but returns string keys/values
    (the upstream returns bytes keys).

    >>> head = 'form-data; name="Test"; '
    >>> parse_options_header(head + 'filename="Test.txt"')[0]
    'form-data'
    >>> parse_options_header(head + 'filename="Test.txt"')[1]['name']
    'Test'

    """
    if not header:
        return "", {}

    content_type, raw_options = _pm_parse_options_header(header)

    # python-multipart returns bytes keys/values — normalize to str.
    result: dict[str, str] = options or {}
    for key, value in raw_options.items():
        k = key.decode("latin-1") if isinstance(key, bytes) else str(key)
        v = value.decode("latin-1") if isinstance(value, bytes) else str(value)
        result[k] = v

    ct = content_type.decode("latin-1") if isinstance(content_type, bytes) else str(content_type)
    return ct, result


def _safe_decode(src: bytes | bytearray, codec: str) -> str:
    """Decode bytes, falling back to latin-1 on errors."""
    try:
        return src.decode(codec)
    except (UnicodeDecodeError, LookupError):
        return src.decode("latin-1")


# ── MultipartPart ────────────────────────────────────────────────────


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
            fields this is a ``BytesIO``; for larger uploads it is a
            ``SpooledTemporaryFile`` that may spill to disk.

        content_type:
            The Content-Type of this part, or None.

        size:
            Number of data bytes written so far.

        headers:
            The raw headers of this part as a list of (name, value) tuples.

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
        self.headers: list[tuple[bytes, bytes]] = []

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


# ── Async Multipart Parser ───────────────────────────────────────────


class MultipartParser:
    """Async multipart/form-data parser.

    Parses a multipart stream using python-multipart's callback-based
    parser, collecting parts into ``MultipartPart`` objects.

    Arguments:

        stream:
            An async generator yielding body chunks.

        boundary:
            The multipart boundary string.

        encoding:
            Default charset for decoding field values.

        max_files:
            Maximum number of file fields allowed.

        max_fields:
            Maximum number of non-file fields allowed.

        max_part_size:
            Maximum size in bytes for a non-file field.

        memfile_limit:
            Threshold in bytes before spooling file data to disk.

    """

    def __init__(
        self,
        stream: AsyncGenerator[bytes, None],
        boundary: str | bytes,
        *,
        encoding: str = "utf-8",
        max_files: int = 1000,
        max_fields: int = 1000,
        max_part_size: int = 2 ** 20,
        memfile_limit: int = 2 ** 20,
    ):
        self.stream = stream
        self.boundary = boundary
        self.encoding = encoding
        self.max_files = max_files
        self.max_fields = max_fields
        self.max_part_size = max_part_size
        self.memfile_limit = memfile_limit

        self._current_part = MultipartPart(encoding=encoding)
        self._current_partial_header_name: bytes = b""
        self._current_partial_header_value: bytes = b""
        self._current_files = 0
        self._current_fields = 0

        self.items: list[tuple[str, str | MultipartPart]] = []
        self._file_parts_to_write: list[tuple[MultipartPart, bytes]] = []
        self._file_parts_to_finish: list[MultipartPart] = []
        self._files_to_close_on_error: list[SpooledTemporaryFile[bytes]] = []

    # -- python-multipart callbacks (sync) --

    def on_part_begin(self) -> None:
        self._current_part = MultipartPart(
            encoding=self.encoding,
            memfile_limit=self.memfile_limit,
        )

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        message_bytes = data[start:end]
        part = self._current_part
        if part.file is None:
            # Still accumulating headers — shouldn't happen after on_headers_finished,
            # but guard against it.
            return
        if part.filename is None:
            # Non-file field: accumulate in memory with size check.
            if part.size + len(message_bytes) > self.max_part_size:
                raise MultipartError(
                    f"Field exceeded maximum size of {self.max_part_size} bytes."
                )
            part.file.write(message_bytes)
            part.size += len(message_bytes)
        else:
            # File field: queue write for async flush.
            self._file_parts_to_write.append((part, message_bytes))

    def on_part_end(self) -> None:
        part = self._current_part
        if part.filename is None:
            # Non-file field: store decoded value.
            if part.file:
                part.file.seek(0)
                self.items.append((
                    part.name,
                    _safe_decode(part.file.read(), self.encoding),
                ))
        else:
            # File field: will be seeked to 0 in async flush.
            self._file_parts_to_finish.append(part)
            self.items.append((part.name, part))

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._current_partial_header_name += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._current_partial_header_value += data[start:end]

    def on_header_end(self) -> None:
        field = self._current_partial_header_name.lower()
        self._current_part.headers.append(
            (field, self._current_partial_header_value)
        )
        self._current_partial_header_name = b""
        self._current_partial_header_value = b""

    def on_headers_finished(self) -> None:
        part = self._current_part

        # Find Content-Disposition to extract name and filename.
        content_disposition = b""
        for hname, hval in part.headers:
            if hname == b"content-disposition":
                content_disposition = hval
                break

        if not content_disposition:
            raise MultipartError("Content-Disposition header is missing.")

        _, options = _pm_parse_options_header(content_disposition)

        try:
            part.name = _safe_decode(options[b"name"], self.encoding)
        except KeyError:
            raise MultipartError(
                'The Content-Disposition header field "name" must be provided.'
            ) from None

        if b"filename" in options:
            self._current_files += 1
            if self._current_files > self.max_files:
                raise MultipartError(
                    f"Too many files. Maximum number of files is {self.max_files}."
                )
            part.filename = _safe_decode(options[b"filename"], self.encoding)
            tempfile = SpooledTemporaryFile(max_size=self.memfile_limit)
            self._files_to_close_on_error.append(tempfile)
            part.file = tempfile
            # Extract Content-Type for file parts.
            for hname, hval in part.headers:
                if hname == b"content-type":
                    part.content_type = hval.decode("latin-1")
                    break
        else:
            self._current_fields += 1
            if self._current_fields > self.max_fields:
                raise MultipartError(
                    f"Too many fields. Maximum number of fields is {self.max_fields}."
                )
            part.file = BytesIO()

    def on_end(self) -> None:
        pass

    # -- Async parse method --

    async def parse(self) -> list[tuple[str, str | MultipartPart]]:
        """Parse the multipart stream and return a list of (name, value) pairs.

        For non-file fields, value is a decoded string.
        For file fields, value is a ``MultipartPart`` instance.
        """
        callbacks = {
            "on_part_begin": self.on_part_begin,
            "on_part_data": self.on_part_data,
            "on_part_end": self.on_part_end,
            "on_header_field": self.on_header_field,
            "on_header_value": self.on_header_value,
            "on_header_end": self.on_header_end,
            "on_headers_finished": self.on_headers_finished,
            "on_end": self.on_end,
        }

        parser = multipart.MultipartParser(self.boundary, callbacks)
        try:
            async for chunk in self.stream:
                if not chunk:
                    break
                parser.write(chunk)
                # Flush queued file writes (must be done here, outside
                # the sync callbacks, to avoid blocking the event loop
                # if SpooledTemporaryFile spills to disk).
                for part, data in self._file_parts_to_write:
                    assert part.file
                    part.file.write(data)
                    part.size += len(data)
                for part in self._file_parts_to_finish:
                    assert part.file
                    part.file.seek(0)
                self._file_parts_to_write.clear()
                self._file_parts_to_finish.clear()
            parser.finalize()
        except MultipartError:
            for file in self._files_to_close_on_error:
                file.close()
            raise

        return self.items
