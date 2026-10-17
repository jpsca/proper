"""The parsers of request bodies: what doesn't fit the buffers a thread
starts with, and the edges of what Python makes of the parts."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from proper import _native
from proper.core.request.formparser import (
    parse_multipart_sync,
    parse_options_header,
    parse_urlencoded,
)
from proper.errors import MultipartError


def on_a_new_thread(func, *args, **kwargs):
    """A new thread starts with buffers of `BUFFER_SIZE` and room for
    `PARTS` parts and `PARAMS` parameters."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(func, *args, **kwargs).result()


def multipart(parts, boundary="b"):
    body = b""
    for name, value in parts:
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += value + b"\r\n"
    return body + f"--{boundary}--\r\n".encode()


def test_an_urlencoded_body_larger_than_the_buffer():
    value = "x" * (2 * _native.BUFFER_SIZE)
    form = on_a_new_thread(parse_urlencoded, f"a={value}&b=2".encode())
    assert (form["a"], form["b"]) == (value, "2")


def test_a_header_larger_than_the_buffer():
    value = "v" * _native.BUFFER_SIZE
    ctype, options = on_a_new_thread(parse_options_header, f'text/plain; long="{value}"')
    assert (ctype, options) == ("text/plain", {"long": value})


def test_more_parameters_than_there_is_room_for():
    count = _native.PARAMS * 2
    header = "text/plain; " + "; ".join(f"p{i}={i}" for i in range(count))
    _, options = on_a_new_thread(parse_options_header, header)
    assert options == {f"p{i}": str(i) for i in range(count)}


def test_more_parts_than_there_is_room_for():
    count = _native.PARTS * 3
    body = multipart([(f"f{i}", str(i).encode()) for i in range(count)])
    form = on_a_new_thread(parse_multipart_sync, body, {"boundary": "b"})
    assert [form[f"f{i}"] for i in range(count)] == [str(i) for i in range(count)]


def test_names_larger_than_the_buffer():
    names = [f"{i}-" + "n" * 1000 for i in range(_native.BUFFER_SIZE // 1000 * 2)]
    body = multipart([(name, b"v") for name in names])
    form = on_a_new_thread(parse_multipart_sync, body, {"boundary": "b"})
    assert list(form) == names


def test_a_boundary_that_is_not_latin1():
    with pytest.raises(MultipartError, match="latin-1"):
        parse_multipart_sync(b"", {"boundary": "日本"})


def test_a_header_that_is_not_latin1():
    """A `str` header from an app's own code, not from the network."""
    assert parse_options_header('text/plain; name="日本"') == (
        "text/plain", {"name": "日本".encode().decode("latin-1")}
    )


def test_the_headers_of_a_part():
    body = (
        b"--b\r\n"
        b'Content-Disposition: form-data; name="f"; filename="a.txt"\r\n'
        b"Content-Type:   text/plain\r\n"
        b"X-Empty:\r\n"
        b"\r\n"
        b"data\r\n"
        b"--b--\r\n"
    )
    part = parse_multipart_sync(body, {"boundary": "b"})["f"]
    assert part.content_type == "text/plain"
    assert part.headers == [
        (b"content-disposition", b'form-data; name="f"; filename="a.txt"'),
        (b"content-type", b"text/plain"),
        (b"x-empty", b""),
    ]
    assert part.headers is part.headers  # read once
    part.headers = [(b"x", b"y")]
    assert part.headers == [(b"x", b"y")]
    part.close()


def test_an_urlencoded_body_with_as_many_fields_as_allowed():
    form = parse_urlencoded(b"a=1&&b=2&c=3&", max_fields=3)
    assert form.getall("a") + form.getall("b") + form.getall("c") == ["1", "2", "3"]


def test_an_urlencoded_body_with_too_many_fields():
    with pytest.raises(MultipartError, match="Maximum number of fields is 3"):
        parse_urlencoded(b"a=1&b=2&c=3&d=4", max_fields=3)
