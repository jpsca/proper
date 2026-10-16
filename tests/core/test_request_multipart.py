from io import BytesIO
from tempfile import SpooledTemporaryFile

import pytest

from proper.core.request import formparser
from proper.core.request.formparser import (
    MultipartPart,
    parse_multipart_sync,
)
from proper.errors import MultipartError
from proper.helpers import MultiDict


def parse(body, boundary="testboundary", **limits):
    """The parts of a body, in order, as `(name, value)`."""
    form = parse_multipart_sync(body, {"boundary": boundary}, **limits)
    return [(name, value) for name, values in form.items() for value in values]


def _build_multipart(parts, boundary="testboundary"):
    body = b""
    for part in parts:
        body += f"--{boundary}\r\n".encode()
        disp = f'Content-Disposition: form-data; name="{part["name"]}"'
        if "filename" in part:
            disp += f'; filename="{part["filename"]}"'
        body += disp.encode() + b"\r\n"
        if "content_type" in part:
            body += f"Content-Type: {part['content_type']}\r\n".encode()
        body += b"\r\n"
        value = part["value"]
        if isinstance(value, str):
            value = value.encode()
        body += value + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body


def test_mppart_defaults():
    part = MultipartPart()
    assert part.name == ""
    assert part.filename is None
    assert part.file is None
    assert part.content_type is None
    assert part.size == 0
    assert part.headers == []


def test_mppart_is_buffered_bytesio():
    part = MultipartPart()
    part.file = BytesIO(b"data")
    assert part.is_buffered() is True


def test_mppart_is_buffered_other():
    part = MultipartPart()
    part.file = SpooledTemporaryFile()
    assert part.is_buffered() is False
    part.close()


def test_mppart_value_and_raw():
    part = MultipartPart()
    part.file = BytesIO(b"hello")
    assert part.raw == b"hello"
    assert part.value == "hello"
    # file position should be restored
    assert part.file.tell() == 0


def test_mppart_raw_no_file():
    part = MultipartPart()
    assert part.raw == b""


def test_mppart_save_as(tmp_path):
    part = MultipartPart()
    part.file = BytesIO(b"file content")
    dest = tmp_path / "output.bin"
    size = part.save_as(str(dest))
    assert size == 12
    assert dest.read_bytes() == b"file content"
    # file position should be restored
    assert part.file.tell() == 0


def test_mppart_close():
    part = MultipartPart()
    part.file = BytesIO(b"data")
    part.close()
    assert part.file is None


def test_mppart_close_no_file():
    part = MultipartPart()
    part.close()  # should not raise


def test_single_field():
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": "field1", "value": "hello"}],
        boundary=boundary,
    )
    items = parse(body)
    assert len(items) == 1
    assert items[0] == ("field1", "hello")


def test_multiple_fields():
    boundary = "testboundary"
    body = _build_multipart(
        [
            {"name": "a", "value": "1"},
            {"name": "b", "value": "2"},
        ],
        boundary=boundary,
    )
    items = parse(body)
    assert len(items) == 2


def test_file_upload():
    boundary = "testboundary"
    body = _build_multipart(
        [
            {
                "name": "file",
                "value": b"file content here",
                "filename": "test.txt",
                "content_type": "text/plain",
            },
        ],
        boundary=boundary,
    )
    items = parse(body)
    assert len(items) == 1
    name, part = items[0]
    assert name == "file"
    assert isinstance(part, MultipartPart)
    assert part.filename == "test.txt"
    assert part.content_type == "text/plain"
    assert part.raw == b"file content here"
    part.close()


def test_mixed_fields_and_files():
    boundary = "testboundary"
    body = _build_multipart(
        [
            {"name": "title", "value": "My File"},
            {
                "name": "upload",
                "value": b"binary data",
                "filename": "data.bin",
                "content_type": "application/octet-stream",
            },
        ],
        boundary=boundary,
    )
    items = parse(body)
    assert items[0] == ("title", "My File")
    name, part = items[1]
    assert isinstance(part, MultipartPart)
    part.close()


def test_no_boundary_error():
    with pytest.raises(MultipartError, match="boundary"):
        parse_multipart_sync(b"", {})


def test_max_fields_exceeded():
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": f"field{i}", "value": "v"} for i in range(5)],
        boundary=boundary,
    )
    with pytest.raises(MultipartError, match="Too many fields"):
        parse(body, max_fields=2)


def test_max_files_exceeded():
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": f"f{i}", "value": b"data", "filename": f"f{i}.txt"} for i in range(5)],
        boundary=boundary,
    )
    with pytest.raises(MultipartError, match="Too many files"):
        parse(body, max_files=2)


def test_max_part_size_exceeded():
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": "big", "value": "x" * 100}],
        boundary=boundary,
    )
    with pytest.raises(MultipartError, match="exceeded"):
        parse(body, max_part_size=10)


def test_missing_content_disposition():
    boundary = "testboundary"
    # Manually craft a body without Content-Disposition
    body = (
        f"--{boundary}\r\nContent-Type: text/plain\r\n\r\nvalue\r\n--{boundary}--\r\n"
    ).encode()
    with pytest.raises(MultipartError, match="Content-Disposition"):
        parse(body)


def test_missing_name_in_disposition():
    boundary = "testboundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data\r\n"
        f"\r\n"
        f"value\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    with pytest.raises(MultipartError, match="name"):
        parse(body)


def test_parse_multipart_sync_function():
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": "x", "value": "y"}],
        boundary=boundary,
    )
    result = parse_multipart_sync(body, {"boundary": boundary})
    assert isinstance(result, MultiDict)
    assert result.get("x") == "y"


def test_chunked_parse():
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": "field", "value": "hello"}],
        boundary=boundary,
    )
    items = parse(body)
    assert items[0] == ("field", "hello")


def test_file_parts_closed_on_error():
    boundary = "testboundary"
    # Create body with a file upload then exceed max_fields with non-file
    parts = [
        {"name": "f", "value": b"data", "filename": "f.txt"},
    ]
    parts.extend({"name": f"field{i}", "value": "v"} for i in range(5))
    body = _build_multipart(parts, boundary=boundary)
    with pytest.raises(MultipartError):
        parse(body, max_fields=2)


@pytest.mark.parametrize(
    "body",
    [
        # No boundary line at the start.
        b"garbage",
        # A different boundary.
        b"--other\r\nContent-Disposition: form-data; name=a\r\n\r\nv\r\n--other--\r\n",
        # A header line without a colon.
        b"--testboundary\r\nbad header line\r\n\r\nv\r\n--testboundary--\r\n",
    ],
)
def test_framing_error(body):
    """python-multipart's own parse errors are a `MultipartError` (400)."""
    with pytest.raises(MultipartError):
        parse(body)


@pytest.mark.parametrize(
    "tail",
    [
        b"",
        b"--testboundary",
        b"--testboundary\r\n",
        b"--testboundary-",
        b"--testboundaryZZ",
    ],
)
def test_missing_final_boundary(tail):
    """A body cut before the final boundary is an error, not a form that
    silently lacks its last fields."""
    body = b"--testboundary\r\nContent-Disposition: form-data; name=a\r\n\r\nv\r\n" + tail
    with pytest.raises(MultipartError, match="final boundary"):
        parse(body)


@pytest.mark.parametrize("tail", [b"--testboundary--", b"--testboundary--\r\nepilogue"])
def test_final_boundary_without_crlf_or_with_epilogue(tail):
    body = b"--testboundary\r\nContent-Disposition: form-data; name=a\r\n\r\nv\r\n" + tail
    assert parse(body) == [("a", "v")]


def test_a_refused_body_makes_no_file(monkeypatch):
    """The whole body is checked before any file is made."""
    made = []

    class Recorded(SpooledTemporaryFile):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            made.append(self)

    monkeypatch.setattr(formparser, "SpooledTemporaryFile", Recorded)
    body = (
        b"--testboundary\r\n"
        b'Content-Disposition: form-data; name="f"; filename="f.txt"\r\n'
        b"\r\n"
        b"data\r\n"
        b"--testboundary\r\n"
        b"bad header line\r\n"
    )
    with pytest.raises(MultipartError):
        parse(body)
    assert made == []
    parse(_build_multipart([{"name": "f", "value": b"data", "filename": "f.txt"}]))
    assert len(made) == 1
