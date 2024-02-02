# Based on multipart (0.2.4) by Marcel Hellkamp
# with modifications for the Proper project.
# Licensed under the MIT License.
"""
Parser for multipart/form-data
==============================

This module provides a parser for the multipart/form-data format. It can read
from a file, a socket or a WSGI environment. The parser can be used to replace
cgi.FieldStorage to work around its limitations.
"""
import re
import typing as t
from io import BytesIO
from tempfile import TemporaryFile
from wsgiref.headers import Headers

from proper.errors import MultipartError


def to_bytes(data: str | bytes, enc: str = "utf8") -> bytes:
    if isinstance(data, str):
        data = data.encode(enc)

    return data


def copy_file(
    stream: t.IO[bytes],
    target: t.IO[bytes],
    maxread: int = -1,
    buffer_size: int = 2 * 16,
) -> int:
    """ Read from :stream and write to :target until :maxread or EOF. """
    size, read = 0, stream.read

    while True:
        to_read = buffer_size if maxread < 0 else min(buffer_size, maxread - size)
        part = read(to_read)

        if not part:
            return size

        target.write(part)
        size += len(part)


RE_SPECIAL = re.escape('()<>@,;:"\\/[]?={} \t')
RX_SPECIAL = re.compile(r"[%s]" % RE_SPECIAL)
RE_QUOTED_STRING = r'"(?:\\.|[^"])*"'  # Quoted string
RE_VALUE = r"(?:[^%s]+|%s)" % (RE_SPECIAL, RE_QUOTED_STRING)  # Save or quoted string
RE_OPTION = r"(?:;|^)\s*([^%s]+)\s*=\s*(%s)" % (RE_SPECIAL, RE_VALUE)
RX_OPTION = re.compile(RE_OPTION)  # key=value part of an Content-Type like header


def header_quote(val: str) -> str:
    r"""

    >>> header_quote("foo")
    'foo'
    >>> header_quote('foo"bar')
    '"foo\\"bar"'

    """
    if not RX_SPECIAL.search(val):
        return val

    return '"' + val.replace("\\", "\\\\").replace('"', '\\"') + '"'


def header_unquote(val: str) -> str:
    r"""

    >>> header_unquote('"foo"')
    'foo'
    >>> header_unquote(r'"foo\\"bar"')
    'foo"bar'

    """
    if val[0] == val[-1] == '"':
        val = val[1:-1]
        return val.replace("\\\\", "\\").replace('\\"', '"')

    return val


def parse_options_header(
    header: str,
    options: dict[str, str] | None = None
) -> tuple[str, dict[str, str]]:
    r"""

    >>> head = 'form-data; name="Test"; '
    >>> parse_options_header(head+'filename="Test.txt"')[0]
    'form-data'
    >>> parse_options_header(head+'filename="Test.txt"')[1]['name']
    'Test'
    >>> parse_options_header(head+'filename="Test.txt"')[1]['filename']
    'Test.txt'
    >>> parse_options_header(head+'FileName="Te\\"st.txt"')[1]['filename']
    'Te"st.txt'

    """
    if ";" not in header:
        return header.lower().strip(), {}

    content_type, tail = header.split(";", 1)
    options = options or {}

    for match in RX_OPTION.finditer(tail):
        key = match.group(1).lower()
        value = header_unquote(match.group(2))
        options[key] = value

    return content_type, options


class MultipartParser(object):
    def __init__(
        self,
        stream: t.IO[bytes],
        boundary: str | bytes,
        content_length: int = -1,
        *,
        disk_limit: int = 2 ** 30,
        mem_limit: int = 2 ** 20,
        memfile_limit: int = 2 ** 18,
        buffer_size: int = 2 ** 16,
        encoding: str = "latin1",
    ):
        """Parse a multipart/form-data byte stream.

        This object is an iterator over the parts of the message.

        Arguments:

        - stream:
            A file-like stream. Must implement `.read(size)`.

        - boundary:
            The multipart boundary as a byte string.

        - content_length:
            The maximum number of bytes to read.

        """
        self.stream = stream
        self.boundary = boundary
        self.content_length = content_length
        self.disk_limit = disk_limit
        self.memfile_limit = memfile_limit
        self.mem_limit = min(mem_limit, self.disk_limit)
        self.buffer_size = min(buffer_size, self.mem_limit)
        self.encoding = encoding

        if self.buffer_size - 6 < len(boundary):  # "--boundary--\r\n"
            raise MultipartError("Boundary does not fit into buffer_size.")

        self._done = []
        self._part_iter = None

    def __iter__(self) -> t.Iterator["MultipartPart"]:
        """ Iterate over the parts of the multipart message. """
        if not self._part_iter:
            self._part_iter = self._iterparse()

        for part in self._done:
            yield part

        for part in self._part_iter:
            self._done.append(part)
            yield part

    def parts(self) -> list["MultipartPart"]:
        """ Returns a list with all parts of the multipart message. """
        return list(self)

    def get(self, name: str, default: t.Any = None) -> t.Any:
        """ Return the first part with that name or a default value (None). """
        for part in self:
            if name == part.name:
                return part

        return default

    def get_all(self, name: str) -> list["MultipartPart"]:
        """ Return a list of parts with that name. """
        return [p for p in self if p.name == name]

    def _lineiter(self) -> t.Iterator[t.Tuple[bytes, bytes]]:
        """ Iterate over a binary file-like object line by line. Each line is
            returned as a (line, line_ending) tuple. If the line does not fit
            into self.buffer_size, line_ending is empty and the rest of the line
            is returned with the next iteration.
        """
        read = self.stream.read
        maxread, maxbuf = self.content_length, self.buffer_size
        buffer = b""  # buffer for the last (partial) line

        while True:
            data = read(maxbuf if maxread < 0 else min(maxbuf, maxread))
            maxread -= len(data)
            lines = (buffer + data).splitlines(True)
            len_first_line = len(lines[0])

            # be sure that the first line does not become too big
            if len_first_line > self.buffer_size:
                # at the same time don't split a '\r\n' accidentally
                if len_first_line == self.buffer_size + 1 and lines[0].endswith(b"\r\n"):
                    splitpos = self.buffer_size - 1
                else:
                    splitpos = self.buffer_size
                lines[:1] = [lines[0][:splitpos], lines[0][splitpos:]]

            if data:
                buffer = lines[-1]
                lines = lines[:-1]

            for line in lines:
                if line.endswith(b"\r\n"):
                    yield line[:-2], b"\r\n"
                elif line.endswith(b"\n"):
                    yield line[:-1], b"\n"
                elif line.endswith(b"\r"):
                    yield line[:-1], b"\r"
                else:
                    yield line, b""

            if not data:
                break

    def _iterparse(self) -> t.Iterable["MultipartPart"]:
        lines, line = self._lineiter(), ""
        separator = b"--" + to_bytes(self.boundary)
        terminator = b"--" + to_bytes(self.boundary) + b"--"

        # Consume first boundary. Ignore any preamble, as required by RFC
        # 2046, section 5.1.1.
        for line, _nl in lines:
            if line in (separator, terminator):
                break
        else:
            raise MultipartError("Stream does not contain boundary")

        # Check for empty data
        if line == terminator:
            for _ in lines:
                raise MultipartError("Data after end of stream")
            return

        # For each part in stream...
        mem_used, disk_used = 0, 0  # Track used resources to prevent DoS
        is_tail = False  # True if the last line was incomplete (cutted)

        opts = {
            "buffer_size": self.buffer_size,
            "memfile_limit": self.memfile_limit,
            "encoding": self.encoding,
        }

        part = MultipartPart(**opts)

        for line, nl in lines:
            if line == terminator and not is_tail:
                if part.file:
                    part.file.seek(0)
                yield part
                break

            elif line == separator and not is_tail:
                if part.is_buffered():
                    mem_used += part.size
                else:
                    disk_used += part.size

                if part.file:
                    part.file.seek(0)
                yield part

                part = MultipartPart(**opts)

            else:
                is_tail = not nl  # The next line continues this one
                try:
                    part.feed(line, nl)

                    if part.is_buffered():
                        if part.size + mem_used > self.mem_limit:
                            raise MultipartError("Memory limit reached.")
                    elif part.size + disk_used > self.disk_limit:
                        raise MultipartError("Disk limit reached.")
                except MultipartError:
                    part.close()
                    raise
        else:
            # If we run off the end of the loop, the current MultipartPart
            # will not have been yielded, so it's our responsibility to
            # close it.
            part.close()

        if line != terminator:
            raise MultipartError("Unexpected end of multipart stream.")


class MultipartPart(object):
    file: t.IO[bytes] | None = None

    def __init__(
        self,
        buffer_size: int = 2 ** 16,
        memfile_limit: int = 2 ** 18,
        encoding: str = "latin1",
    ):
        self.headerlist = []
        self.headers = None
        self.size = 0
        self._buf = b""
        self.disposition = None
        self.name = None
        self.filename = None
        self.content_type = None
        self.encoding = encoding
        self.memfile_limit = memfile_limit
        self.buffer_size = buffer_size
        self.content_length = -1

    def feed(self, bline: bytes, nl: bytes = b"") -> None:
        if self.file:
            return self.write_body(bline, nl)

        return self.write_header(bline, nl)

    def write_header(self, bline: bytes, nl: bytes) -> None:
        line = bline.decode(self.encoding)

        if not nl:
            raise MultipartError("Unexpected end of line in header.")

        if not line.strip():  # blank line -> end of header segment
            self.finish_header()
        elif line[0] in " \t" and self.headerlist:
            name, value = self.headerlist.pop()
            self.headerlist.append((name, value + line.strip()))
        else:
            if ":" not in line:
                raise MultipartError("Syntax error in header: No colon.")

            name, value = line.split(":", 1)
            self.headerlist.append((name.strip(), value.strip()))

    def write_body(self, bline: bytes, nl: bytes) -> None:
        if not bline and not nl:
            return  # This does not even flush the buffer

        self.size += len(bline) + len(self._buf)
        self.file.write(self._buf + bline)  # type: ignore
        self._buf = nl

        if self.content_length > 0 and self.size > self.content_length:
            raise MultipartError("Size of body exceeds Content-Length header.")

        if self.size > self.memfile_limit and isinstance(self.file, BytesIO):
            # TODO: What about non-file uploads that exceed the memfile_limit?
            self.file, old = TemporaryFile(mode="w+b"), self.file
            old.seek(0)
            copy_file(old, self.file, self.size, self.buffer_size)

    def finish_header(self) -> None:
        self.file = BytesIO()
        self.headers = Headers(self.headerlist)
        content_disposition = self.headers.get("Content-Disposition", "")
        content_type = self.headers.get("Content-Type", "")

        if not content_disposition:
            raise MultipartError("Content-Disposition header is missing.")

        self.disposition, self.options = parse_options_header(content_disposition)
        self.name = self.options.get("name")
        self.filename = self.options.get("filename")
        self.content_type, options = parse_options_header(content_type)
        self.encoding = options.get("charset") or self.encoding
        self.content_length = int(self.headers.get("Content-Length") or "-1")

    def is_buffered(self) -> bool:
        """ Return true if the data is fully buffered in memory."""
        return isinstance(self.file, BytesIO)

    @property
    def value(self) -> str:
        """ Data decoded with the specified charset """

        return self.raw.decode(self.encoding)

    @property
    def raw(self) -> bytes:
        """ Data without decoding """
        if not self.file:
            return b""

        pos = self.file.tell()
        self.file.seek(0)

        try:
            val = self.file.read()
        except IOError:
            raise
        finally:
            self.file.seek(pos)

        return val

    def save_as(self, path: str) -> int:
        assert self.file

        with open(path, "wb") as fp:
            pos = self.file.tell()

            try:
                self.file.seek(0)
                size = copy_file(self.file, fp)
            finally:
                self.file.seek(pos)

        return size

    def close(self):
        if self.file:
            self.file.close()
            self.file = None
